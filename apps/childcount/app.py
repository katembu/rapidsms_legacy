#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: dgelvin

import re
import time
from datetime import date, datetime, timedelta

from django.utils.translation import ugettext as _, activate
from django.utils.translation import ungettext
from django.contrib.auth.models import Group
from django.db import models
from reversion import revision

import rapidsms
from reporters.models import Reporter
from locations.models import Location

from childcount.models import Configuration as Cfg
from childcount.models import Patient,  CHW
from childcount.forms import *
from childcount.commands import *
from childcount.exceptions import *
from childcount.utils import respond_exceptions, KeywordMapper
from childcount.utils import send_msg


class App (rapidsms.app.App):
    """Main ChildCount App
    """
    DEFAULT_LANGUAGE = 'en'
    FORM_PREFIX = '+'

    # The time at which we decide this is a new encounter, in MINUTES
    ENCOUNTER_TIMEOUT = 6 * 60

    commands = []
    forms = []

    def configure(self, title='ChildCount', tab_link='/childcount', \
                  forms=None, commands=None, serverlet_port = None, \
                   serverlet_host = None):
        """Load CC+ forms and commands"""

        if forms is not None:
            forms = forms.replace(' ', '').split(',')
            for form in forms:
                try:
                    self.forms.append(eval(form))
                except NameError:
                    self.debug(_(u'%s form not found.') % form)
        if commands is not None:
            commands = commands.replace(' ', '').split(',')
            for command in commands:
                try:
                    self.commands.append(eval(command))
                except:
                    self.debug(_(u'%s command not found.') % command)

    def start(self):
        self.command_mapper = KeywordMapper()
        self.form_mapper = KeywordMapper()
        self.form_mapper.add_classes(self.forms)
        self.command_mapper.add_classes(self.commands)

    def parse(self, message):
        """Parse and annotate messages in the parse phase."""
        pass

    @respond_exceptions
    @revision.create_on_success
    def handle(self, message):
        handled = False

        if message.text is None:
            return False

        # If this is coming from debackend, it will have message.chw and
        # message.encounter_date.  Otherwise, the reporter is the chw,
        # and the encounter date is from the backend
        if 'chw' in message.__dict__:

            try:
                chw = CHW.objects.get(pk=message.chw)
            except CHW.DoesNotExist:
                message.respond(_(u"Problem getting CHW from backend."), \
                                'error')
                return handled

            reporter = chw.reporter
            message.reporter = reporter
        else:
            reporter = message.persistant_connection.reporter

        if reporter and reporter.language:
            lang = reporter.language
            print "))))))))))%s" % lang
        else:
            lang = self.DEFAULT_LANGUAGE

            # store default language in reporter during session
            if reporter:
                reporter.language = lang

        activate(lang)

        # Use the datetime coming from the backend as the date. Times
        # from the backend are UTC naive. We convert it to localtime
        # naive. The system clock of the server must be set to the
        # local time zone for this to work. This won't work correctly
        # for locations with DST.
        message.date = message.date - timedelta(seconds=time.timezone)

        # Check if coming from debackend
        is_debackend = ('chw' in message.__dict__)

        # Check if we're allowing submissions for patients
        # by CHWs other than their own
        try:
            allow = Cfg.objects.get(key='allow_third_party_submissions')
        except Cfg.DoesNotExist:
            allow_3rd_party = True
        else:
            allow_3rd_party = (allow.value.lower() == 'true')

        # If coming from debackend...
        if is_debackend:
            try: 
                rep = Reporter.objects.get(username=message.identity)
            except Reporter.DoesNotExist:
                message.respond(_(u"Invalid user logged in."), 'error')
                return handled
    
            # Data entry clerk forgot to set the CHW
            if chw.pk == rep.pk:
                message.respond(_(u"%(fname)s, "
                                "you must select a CHW other than yourself "
                                "at the bottom of the data entry screen.") % \
                                {'fname': rep.first_name}, \
                    'error')
                return handled

        # Validate debackend encounter date
        if 'encounter_date' in message.__dict__:
            try:
                edate = datetime.strptime(message.encounter_date, \
                                         "%Y-%m-%d")
            except ValueError:
                message.respond(_(u"Problem getting encounter_date from "\
                                   "backend."), 'error')
                return handled

            # Don't allow future dates
            if edate.date() > date.today():
                message.respond(_(u"You cannot select an encounter date that is "
                    "in the future."),
                    'error')
                return handled
 
        # Set the user of revision, equal to the user object of the reporter
        if reporter:
            revision.user = reporter.user_ptr

        # make lower case, strip, and remove duplicate spaces
        input_text = re.sub(r'\s{2,}', ' ', message.text.strip().lower())

        ### Forms
        split_regex = re.compile( \
         r'^\s*((?P<health_ids>.*?)\s*)??(?P<forms>%(form_prefix)s.+$)' % \
             {'form_prefix': re.escape(self.FORM_PREFIX)})
        forms_match = split_regex.match(input_text)

        if forms_match:
            handled = True
            if not reporter:
                message.respond(_(u"You must register before you can send"\
                                  u" reports."), 'error')
                return handled

            chw = reporter.chw

            if 'encounter_date' in message.__dict__:
                try:
                    edate = datetime.strptime(message.encounter_date, \
                                             "%Y-%m-%d")
                    # set it to midday on that day...
                    message.date = edate + timedelta(hours=12)
                except ValueError:
                    message.respond(_(u"Problem getting encounter_date from "\
                                       "backend."), 'error')
                    return handled

            encounter_date = message.date

            health_ids_text = forms_match.groupdict()['health_ids']
            forms_text = forms_match.groupdict()['forms']
            if health_ids_text:
                health_ids = re.findall(r'\w+', health_ids_text)
            else:
                health_ids = []

            form_groups_regex = re.compile( \
                r'%(form_prefix)s\s?(\w+.*?)(?=\s*%(form_prefix)s|$)' % \
                 {'form_prefix': re.escape(self.FORM_PREFIX)})

            forms = []
            for group in form_groups_regex.findall(forms_text):
                params = re.split(r'\s+', group)
                forms.append(params)

            # okay, health_ids is a list containing all health ids:
            # i.e: ['df2d', 'se23', 'di24']

            # forms is a list of lists containing the forms and
            # thier params:
            # i.e: [['birth', 'p', 'm'], ['h', 'y'], ['mob', '12345678']]

            # Right now, we are only going to accept a single health ID.
            if len(health_ids) != 1:
                message.respond(_(u"Error: Message not understood. " \
                                   "Your message must start with " \
                                   "a single health ID, followed by a space " \
                                   "then a %(pre)s, then the keyword of the " \
                                   "form you are sending.") % \
                                   {'pre': self.FORM_PREFIX}, 'error')
                return handled
            health_id = health_ids[0]

            failed_forms = []
            successful_forms = []

            pre_processed_form_objects = []
            for params in forms:
                keyword = params[0]

                if keyword not in self.form_mapper.get_keywords(lang):
                    failed_forms.append({'keyword': keyword, \
                                        'error': _(u"Not a recognised form.")})
                    continue
                cls = self.form_mapper.get_class(lang, keyword)
                form = cls(message, encounter_date, chw, params, health_id)

                # First process.  This is where PatientRegistration will
                # create the patient records
                try:
                    form.date = encounter_date
                    form.pre_process()
                except CCException, e:
                    pretty_form = '%s%s' % (self.FORM_PREFIX, \
                                            keyword.upper())

                    message.respond(_(u"Error occurred while processing " \
                                      "%(frm)s: %(e)s Please correct and " \
                                      "send all information again.") % \
                                       {'frm': pretty_form, 'e': e}, \
                                        'error')
                    return handled
                pre_processed_form_objects.append(form)

            # Now that we have run pre-process, health_id should point to a
            # valid paitent (new patients are created in the
            # PatientRegistrationForm pre_process method
            try:
                patient = Patient.objects.get(health_id__iexact=health_id)
            except Patient.DoesNotExist:
                message.respond(_(u"%(id)s is not a valid health ID. " \
                                   "Please correct and try again.") % \
                                   {'id': health_id.upper()}, 'error')
                return handled

            if (not allow_3rd_party) and patient.chw != chw:
                message.respond(_(u"Patient %(health_id)s is assigned to " \
                                    "CHW %(real_chw)s.  You [%(fake_chw)s] " \
                                    "can only submit forms for your own " \
                                    "patients.") %\
                                    {'health_id': health_id.upper(),\
                                     'real_chw': patient.chw, \
                                     'fake_chw': chw}, 'error')
                return handled
        

            for form in pre_processed_form_objects:
                keyword = form.params[0]

                try:
                    form.process(patient)
                except CCException, e:
                    failed_forms.append({'keyword': keyword, \
                                         'error': unicode(e), 'e': e})
                else:
                    successful_forms.append({'keyword': keyword, \
                                             'response': form.response, \
                                             'obj': form})


            successful_string = ''
            if successful_forms:
                print successful_forms
                keywords = [self.FORM_PREFIX + f['keyword'].upper() \
                                                   for f in successful_forms]
                successful_string += ', '.join(keywords) + \
                                                _(u" Successfully processed:")

                for form in successful_forms:
                    successful_string += ' [%s]' % form['response']

            failed_string = ''
            send_again = False
            for form in failed_forms:
                failed_string += ' %(pre)s%(keyword)s failed: %(error)s' % \
                                 {'pre': self.FORM_PREFIX, \
                                  'keyword': form['keyword'].upper(), \
                                  'error': form['error']}
                if 'e' in form and not isinstance(form['e'], Inapplicable):
                    send_again = True
            if send_again and len(failed_forms) == 1:
                failed_string += _(" You must resend the form.")
            elif send_again and len(failed_forms) > 1:
                failed_string += _(" You must resend the forms.")

            for form in successful_forms:
                try:
                    form['obj'].post_process(successful_forms)
                except:
                    # any exceptions here should not prevent feedback
                    # fail silently
                    # TODO: Log the exception, notify
                    pass

            health_id_str = u"%s => " % health_id.upper()
            if successful_forms and not failed_forms:
                message.respond(health_id_str + successful_string, 'success')
                return handled
            if failed_forms and not successful_forms:
                message.respond(health_id_str + failed_string, 'error')
                return handled
            else:
                if len(failed_forms) == 1:
                    cnt_failed = _(u"One form failed.")
                else:
                    cnt_failed = _(u"%d forms failed.") % len(failed_forms)

                if len(successful_forms) == 1:
                    cnt_successful = _(u"One successful.")
                else:
                    cnt_successful = _(u"%d forms successful.") % \
                                                        len(successful_forms)
                response = u"%s %s, %s: %s, %s" % (health_id_str, \
                                                cnt_failed, cnt_successful, \
                                                failed_string, \
                                                successful_string)
                message.respond(response, 'warning')
            return handled

        ### Commands
        params = re.split(r'\s+', input_text)
        command = params[0]
        if command in self.command_mapper.get_keywords(lang):
            handled = True
            cls = self.command_mapper.get_class(lang, command)
            obj = cls(message, params)
            try:
                obj.process()
            except CCException, e:
                message.respond(e.message, 'error')
        return handled

    def cleanup(self, message):
        """Perform any clean up after all handlers have run in the
           cleanup phase."""
        pass

    def outgoing(self, message):
        """Handle outgoing message notifications."""
        if message.text.find(' is marked as crashed') != -1:
            msg = _(u"Database Error: please notify the system administrator")
            #alert facilitators
            try:
                g = Group.objects.get(name='Facilitator')
                for user in g.user_set.all():
                    send_msg(user.reporter, msg)
            except Group.DoesNotExist:
                pass

    def stop(self):
        """Perform global app cleanup when the application is stopped."""
        pass

    def ajax_POST_send_message(self, urlparser, post):
       """
       Callback method for sending messages from the webui via the ajax app.
       """
       rep = Reporter.objects.get(pk=post["reporter"])
       pconn = rep.connection()

       # abort if we don't know where to send the message to
       # (if the device the reporter registed with has been
       # taken by someone else, or was created in the WebUI)
       if pconn is None:
           raise Exception("%s is unreachable (no connection)" % rep)

       # attempt to send the message
       # TODO: what could go wrong here?
       be = self.router.get_backend(pconn.backend.slug)
       return be.message(pconn.identity, post["text"]).send()
