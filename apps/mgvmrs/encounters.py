#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: rgaudin

from rapidsms.webui import settings
from django.db.models import Q

from childcount.models import Encounter, Patient
from childcount.models.reports import CCReport, PregnancyReport, PregnancyRegistrationReport, AppointmentReport

from mgvmrs.forms import OpenMRSTransmissionError, OpenMRSConsultationForm, \
                         OpenMRSHouseholdForm, OpenMRSANCForm
from mgvmrs.utils import transmit_form
from mgvmrs.models import User


def has_ancreport(reports):
    for report in reports:
        if isinstance(report, PregnancyRegistrationReport):
            return True
        elif isinstance(report, AppointmentReport):
            return True
    return False


def send_to_omrs(router, *args, **kwargs):
    ''' Forwards Encounter to OpenMRS

    Scheduler callback.

    Fetchs all non-synced Encounter
    Send each to OpenMRS via HTTP '''

    # retrieve mgvmrs configuration
    conf = settings.RAPIDSMS_APPS['mgvmrs']

    try:
        # Form IDs and Field location ID are site-specific
        individual_id = int(conf['individual_id'])
        household_id = int(conf['household_id'])
        ancform_id = int(conf['ancform_id'])
        location_id = int(conf['location_id'])
        identifier_type = int(conf['identifier_type'])
        # provider is a fallback if CHW has no OMRS ID in DB.
        provider_id = int(conf['provider_id'])
    except KeyError:
        raise Exception("Invalid [mgvmrs] configuration")

    # this one is not fatal
    try:
        in_cluster_attribute_id = int(conf['in_cluster_attribute_id'])
    except:
        in_cluster_attribute_id = 10

    # request all non-synced Encounter
    encounters = Encounter.objects.filter(Q(sync_omrs__isnull=True) | \
                                          Q(sync_omrs__in=(None, False)))

    for encounter in encounters:
        # loop only on closed Encounters
        if encounter.is_open:
            continue

        # reports contains actual data for an encounter.
        reports = CCReport.objects.filter(encounter=encounter)

        #is the patient registered? if there are reports it is probably not
        #a new registration. is this really true?
        # DG: No, it's not true.  Specifically, the +BIR report will
        # accompany +NEW for births.  We should always send all data.
        '''
        create = True
        if reports.count():
            create = False
        '''
        create = True

        # select OpenMRS Xform according to Encounter type
        omrsformclass = None
        if encounter.type == Encounter.TYPE_HOUSEHOLD:
            omrsformclass = OpenMRSHouseholdForm
            form_id = household_id
        else:
            if has_ancreport(reports):
                omrsformclass = OpenMRSANCForm
                form_id = ancform_id
            else:
                omrsformclass = OpenMRSConsultationForm
                form_id = individual_id

        try:
            # retrieve CHW from local mapping.
            provider = int(User.objects.get(chw=encounter.chw).openmrs_id)
        except User.DoesNotExist:
            # use fall-back ID from config
            provider = provider_id

        # create form
        omrsform = omrsformclass(create, encounter.patient.health_id, \
                                    location_id,
                                    provider,
                                    encounter.encounter_date, \
                                    encounter.patient.dob, \
                                    bool(encounter.patient.estimated_dob), \
                                    encounter.patient.last_name, \
                                    encounter.patient.first_name, '', \
                                    encounter.patient.gender, \
                                    encounter.patient.location.name.title(), \
                                    '1065')
        # assign site-specific ID
        omrsform.openmrs__form_id = form_id
        omrsform.patient___identifier_type = identifier_type
        omrsform.patient__in_cluster_id = in_cluster_attribute_id

        # each report contains reference to OMRS fields
        for report in reports:
            omrsdict = report.get_omrs_dict()
            for key in omrsdict:
                value = omrsdict[key]
                omrsform.assign(key, value)

        # send xform to omrs and change sync status
        try:
            transmit_form(omrsform)
            encounter.sync_omrs = True
            encounter.save()
            router.log('DEBUG', \
                          u"Successfuly sent XForm to OpenMRS: %s" % encounter)
        except OpenMRSTransmissionError, e:
            #TODO : Log this error
            router.log('DEBUG', omrsform.render())
            router.log('DEBUG', e)
            encounter.sync_omrs = False
            encounter.save()
            continue
