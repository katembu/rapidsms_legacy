# coding=utf8

from django.db import models

class Zone(models.Model):
    name        = models.CharField(max_length=10, unique=True)
    zone        = models.ForeignKey('Zone', blank=True, null=True, related_name="related_zone")

    def __unicode__(self):
        return self.name

class BoardTigi(models.Model):
    name        = models.CharField(max_length=10, primary_key=True, db_index=True)
    mobile      = models.CharField(max_length=16, db_index=True, unique=True)
    credit      = models.IntegerField(default=0)
    active      = models.BooleanField(default=True)
    zone        = models.ForeignKey(Zone)
    
    def __unicode__(self):
        return self.name

    @classmethod
    def by_mobile (cls, mobile):
        try:
            return cls.objects.get(mobile=mobile, active=True)
        except models.ObjectDoesNotExist:
            return None

class Announcement(models.Model):
    sender      = models.ForeignKey("BoardTigi", related_name="%(class)s_related_sender")
    recipients  = models.ManyToManyField("BoardTigi", related_name="%(class)s_related_recipients")
    text        = models.CharField(max_length=140)
    date        = models.DateTimeField()
    price       = models.IntegerField(default=0)
    sent        = models.BooleanField()

    def __unicode__(self):
        return "%s (%s)" % (self.sender, self.date.strftime("%c"))

class SysAdmin(models.Model):
    mobile      = models.CharField(max_length=16, primary_key=True)
    name        = models.CharField(max_length=20)

    def __unicode__(self):
        return self.name

    @classmethod
    def granted(cls, mobile):
        try:
            return cls.objects.get(mobile=mobile)
        except models.ObjectDoesNotExist:
            return None

