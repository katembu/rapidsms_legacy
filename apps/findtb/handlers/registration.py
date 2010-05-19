#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: dgelvin

from django.contrib.auth.models import User, Group

from locations.models import Location, LocationType
from reporters.models import Reporter

from findtb.models import *
from findtb.utils import *
from findtb.exceptions import *


CLINICIAN_KEYWORD = 'cli'
DTU_LAB_TECH_KEYWORD = 'lab'
DISTRICT_TB_SUPERVISOR_KEYWORD = 'dtls'
ZONAL_TB_SUPERVISOR_KEYWORD = 'ztls'

KEYWORDS = [
    CLINICIAN_KEYWORD,
    DTU_LAB_TECH_KEYWORD,
    DISTRICT_TB_SUPERVISOR_KEYWORD,
    ZONAL_TB_SUPERVISOR_KEYWORD
]


def handle(keyword, params, message):
    if Configuration.has_key('registration') and \
       Configuration.get('registration') != 'open':
        raise NotAllowed("Registration failed: Registration is currently " \
                         "closed. Please contact NTRL for assistance.")


    text = ' '.join(params)
    regex = r'(?P<prefix>\d+)[ \-,./]+(?P<suffix>\w+)\s+(?P<names>.+)'
    match = re.match(regex, text)

    if not match or not match.groupdict()['prefix'] or \
       not match.groupdict()['suffix']:

        if len(params) > 2:
            raise ParseError("Registraition failed: %s is not a valid " \
                             "DTU code." % params[0].upper())
        else:
            raise ParseError("Registration failed: " \
                             "You must send:\n%s LocationCode " \
                             "Surname FirstName" % keyword.upper())
    try:
        code = '%s-%s' % \
                (match.groupdict()['prefix'], match.groupdict()['suffix'])
        location = Location.objects.get(code=code)
    except Location.DoesNotExist:
        raise BadValue("Registration failed: %(code)s is not a valid " \
                       "location code. Please correct and send again." % \
                       {'code':code})

    names = match.groupdict()['names']
    if len(names.split()) < 2:
        raise ParseError("Registration failed: You must provide both a " \
                         "surname and firstname.")

    reporter = create_or_update_reporter(names, \
                                         message.persistant_connection)

    # Map keywords to auth.group names and to the creation functions
    group_mapping = {
        CLINICIAN_KEYWORD:
            (FINDTBGroup.CLINICIAN_GROUP_NAME, create_clinician),
        DTU_LAB_TECH_KEYWORD:
            (FINDTBGroup.DTU_LAB_TECH_GROUP_NAME, create_lab_tech),
        DISTRICT_TB_SUPERVISOR_KEYWORD:
            (FINDTBGroup.DISTRICT_TB_SUPERVISOR_GROUP_NAME, create_dtls),
        ZONAL_TB_SUPERVISOR_KEYWORD:
            (FINDTBGroup.ZONAL_TB_SUPERVISOR_GROUP_NAME, create_ztls)
    }

    group = FINDTBGroup.objects.get(name=group_mapping[keyword][0])
    creation_function = group_mapping[keyword][1]

    response = creation_function(reporter, group, location)
    message.respond(response, 'success')

    reporter.save()
    message.persistant_connection.reporter = reporter
    message.persistant_connection.save()
    role = Role(location=location, reporter=reporter, group=group)
    role.save()

def create_or_update_reporter(name, persistant_connection):
    reporter = persistant_connection.reporter
    if not reporter:
        reporter = Reporter()

    surname, firstnames, alias = clean_names(name, surname_first=True)

    orig_alias = alias[:20]
    alias = orig_alias.lower()

    if alias != reporter.alias and not \
       re.match(r'%s\d' % alias, reporter.alias):
        n = 1
        while User.objects.filter(username__iexact=alias).count():
            alias = "%s%d" % (orig_alias.lower(), n)
            n += 1
        reporter.alias = alias

    reporter.first_name = firstnames
    reporter.last_name = surname
    reporter.is_active = True
    return reporter

def create_clinician(reporter, group, location):
    reject_non_dtus(location)
    try:
        role = Role.objects.get(group=group, location=location)
    except Role.DoesNotExist:
        pass
    else:
        if role.reporter != reporter:
            raise NotAllowed("Registration failed. %(user)s is already " \
                             "registered as the clinician at %(location)s. " \
                             "Only one clinician can be registered per " \
                             "DTU." % \
                             {'user':role.reporter.full_name(),
                              'location':location})
        else:
            raise NotAllowed("You are already registered as the " \
                             "clinician at %(loc)s. You do not " \
                             "need to register again." % {'loc':location})

    existing_roles = Role.objects.filter(reporter=reporter)
    lab_group = Group.objects.get(name=FINDTBGroup.DTU_LAB_TECH_GROUP_NAME)
    if existing_roles.filter(group=lab_group).count():
        raise NotAllowed("Registration failed. You are already registered " \
                         "as a lab technician. You cannot also register as " \
                         "a clinician.")

    try:
        old = existing_roles.get(group=group)
    except Role.DoesNotExist:
        pass
    else:
        old_location = old.location
        old.delete()
        return "You have moved from %(old)s to %(new)s." % \
               {'old':old_location, 'new':location}

    return "You are now registered as the clinician at %(loc)s." % \
           {'loc': location.name}

def create_lab_tech(reporter, group, location):
    reject_non_dtus(location)

    if Role.objects.filter(group=group, location=location,
                                reporter=reporter).count():
        raise NotAllowed("You are already registered as the " \
                         "lab technician at %(loc)s. You do not " \
                         "need to register again." % {'loc':location})

    existing_roles = Role.objects.filter(reporter=reporter)
    clinic_group = Group.objects.get(name=FINDTBGroup.CLINICIAN_GROUP_NAME)
    if existing_roles.filter(group=clinic_group).count():
        raise NotAllowed("Registration failed. You are already registered " \
                         "as a clinician. You cannot also register as " \
                         "a lab technician.")

    try:
        old = existing_roles.get(group=group)
    except Role.DoesNotExist:
        pass
    else:
        old_location = old.location
        old.delete()
        return "You have moved from %(old)s to %(new)s." % \
               {'old':old_location, 'new':location}

    return "You are now registered as a lab technician at %(loc)s." % \
           {'loc': location.name}

def reject_non_dtus(location):
    if location.type != LocationType.objects.get(name__iexact='dtu'):
        raise BadValue("Registration failed: %(loc)s is not a DTU, it " \
                       "is a %(type)s. You must register with a DTU code." %
                        {'loc':location, 'type':location.type.name})

def create_dtls(reporter, group, location):
    if location.type != LocationType.objects.get(name__iexact='district'):
        raise BadValue("Registration failed: %(loc)s is not a district, it " \
                       "is a %(type)s. You must register with a district " \
                       "code." % {'loc':location, 'type':location.type.name})

def create_ztls(reporter, group, location):
    if location.type != LocationType.objects.get(name__iexact='zone'):
        raise BadValue("Registration failed: %(loc)s is not a zone, it " \
                       "is a %(type)s. You must register with a zone " \
                       "code." % {'loc':location, 'type':location.type.name})
