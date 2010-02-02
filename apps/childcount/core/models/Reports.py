#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: ukanga

'''Report Models

CCReport
PatientReport
'''

from datetime import datetime

from django.db import models
from django.utils.translation import ugettext_lazy as _

from reporters.models import Reporter
from childcount.core.models.Patient import Patient

class CCReport(models.Model):
    '''
    The highest level superclass to be inhereted by all other report classes
    '''
    
    class Meta:
        app_label = 'childcount'
        verbose_name = _(u"ChildCount Report")
        verbose_name_plural = _(u"ChildCount Reports")
        get_latest_by = 'reported_on'
        ordering = ('-reported_on',)

    created_by = models.ForeignKey(Reporter, verbose_name=_(u"Created by"), \
                                   related_name='created_report',
                                   help_text=_(u"Reporter that created the " \
                                                "report"))

    created_on = models.DateTimeField(_(u"Created on"), auto_now_add=True, \
                                      help_text=_(u"When the report was " \
                                                   "created"))

    modified_by = models.ForeignKey(Reporter, verbose_name=_(u"Modified by"), \
                                    related_name='modified_report',
                                    null=True, blank=True, \
                                    help_text=_(u"Reporter that last " \
                                                 "modified the report"))

    modified_on = models.DateTimeField(_(u"Modified on"), auto_now=True, \
                                       null=True, blank=True, \
                                       help_text=_(u"When the report was " \
                                                    "last modified"))


class PatientReport(CCReport):
    '''Patient reports'''
    class Meta:
        app_label = 'childcount'
        verbose_name = _(u"Patient Report")
        verbose_name_plural = _(u"Patient Reports")

    patient = models.ForeignKey(Patient, verbose_name=_(u"Patient"))

class HealthReport(PatientReport):
    class Meta:
        app_label = 'childcount'
        verbose_name = _(u"Health Report")
        verbose_name_plural = _(u"Health Reports")
        
    DANGER_SIGNS_PRESENT = 'S'
    DANGER_SIGNS_NONE = 'N'
    DANGER_SIGNS_UNKOWN = 'U'
    DANGER_SIGNS_UNAVAILABLE = 'W'

    DANGER_SIGNS_CHOICES = (
        (DANGER_SIGNS_PRESENT, _(u"Present")),
        (DANGER_SIGNS_NONE, _(u"None")),
        (DANGER_SIGNS_UNKOWN, _(u"Unknown")),
        (DANGER_SIGNS_UNAVAILABLE, _(u"Unavailable")))
        
    VISITED_CLINIC_YES = 'Y'
    VISITED_CLINIC_NO = 'N'
    VISITED_CLINIC_UNKOWN = 'U'
    VISITED_CLINIC_INPATIENT = 'K'

    VISITED_CLINIC_CHOICES = (
        (VISITED_CLINIC_YES, _(u"Yes")),
        (VISITED_CLINIC_NO, _(u"None")),
        (VISITED_CLINIC_UNKOWN, _(u"Unknown")),
        (VISITED_CLINIC_INPATIENT, _(u"Currently inpatient")))

    danger_signs = models.CharField(_(u"Danger Signs"), max_length=1, \
                                    choices=DANGER_SIGNS_CHOICES)
                                    
    visited_clinic = models.CharField(_(u"Recent Clinic Visit"), max_length=1, \
                                      choices=VISITED_CLINIC_CHOICES, \
                                      help_text=_(u"Did the patient visit a " \
                                                   "health facility since " \
                                                   "the last CHW visit"))

class DeathReport(PatientReport):
    class Meta:
        app_label = 'childcount'
        verbose_name = _(u"Death Report")
        verbose_name_plural = _(u"Death Reports")

    death_date = models.DateField(_(u"Date of death"), \
                                  help_text=_(u"The date of the death " \
                                               "accurate to within the month"))


class PatientRegistrationReport(PatientReport):
    pass