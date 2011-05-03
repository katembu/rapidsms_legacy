'''
Bed net utilization
'''

from django.db.models import F, Q
from django.db.models.aggregates import Sum
from django.utils.translation import ugettext as _

from indicator import Indicator
from indicator import IndicatorPercentage
from indicator import IndicatorDifference
from indicator import QuerySetType

from childcount.models import Patient
from childcount.models.reports import BednetUtilization

class Total(Indicator):
    type_in     = QuerySetType(Patient)
    type_out    = int

    slug        = "total"
    short_name  = _("Bed Net Util. Reports")
    long_name   = _("Total number of bed net utiliaztion reports " \
                    "for unique households during this period")

    @classmethod
    def _value(cls, period, data_in):
        return BednetUtilization\
            .objects\
            .filter(encounter__patient__in=data_in,\
                encounter__encounter_date__range=(period.start, period.end))\
            .values('encounter__patient')\
            .distinct()\
            .count()

class Children(Indicator):
    type_in     = QuerySetType(Patient)
    type_out    = int

    slug        = "children"
    short_name  = _("# Kids")
    long_name   = _("Total number of children monitored this period " \
                    "for bed net utilization")

    @classmethod
    def _value(cls, period, data_in):
        return BednetUtilization\
            .objects\
            .filter(encounter__patient__in=data_in,\
                encounter__encounter_date__range=(period.start, period.end))\
            .aggregate(total=Sum('child_underfive'))['total'] or 0

class ChildrenUsing(Indicator):
    type_in     = QuerySetType(Patient)
    type_out    = int

    slug        = "children_using"
    short_name  = _("# Kids Using")
    long_name   = _("Total number of kids using a "\
                    "bed net this period")

    @classmethod
    def _value(cls, period, data_in):
        return BednetUtilization\
            .objects\
            .filter(encounter__patient__in=data_in,\
                encounter__encounter_date__range=(period.start, period.end))\
            .aggregate(total=Sum('child_lastnite'))['total'] or 0

class ChildrenUsingPerc(IndicatorPercentage):
    type_in     = QuerySetType(Patient)

    slug        = "children_using_perc"
    short_name  = _("% Kids Using Net")
    long_name   = _("Percentage of under fives monitored "\
                    "who used bed nets")
    cls_num     = ChildrenUsing
    cls_den     = Children
