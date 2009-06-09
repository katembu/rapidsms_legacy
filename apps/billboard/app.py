# coding=utf8

import rapidsms
from rapidsms.parsers.keyworder import Keyworder
from rapidsms.message import Message

from ..orangeml.models import *
from models import *

import re
import unicodedata

def _(txt): return unicodedata.normalize('NFKD', txt).encode('ascii','ignore')

def authenticated (func):
    def wrapper (self, message, *args):
        if message.sender:
            return func(self, message, *args)
        else:
            message.respond(_(u"%s ne fait pas partie du réseau.") % message.peer)
            return True
            #return False
    return wrapper

def sysadmin (func):
    def wrapper (self, message, *args):
        if SysAdmin.granted(message.peer):
            return func(self, message, *args)
        else:
            return False
    return wrapper

class HandlerFailed (Exception):
    pass

def recurs_zones(zone):
    zonelist    = []
    all_zones   = Zone.objects.filter(zone=zone)
    for azone in all_zones.iterator():
        zonelist += recurs_zones(azone)
        zonelist.append(azone)
    return zonelist

class App (rapidsms.app.App):

    keyword         = Keyworder()
    MAX_MSG_LEN     = 140
    PRICE_PER_BOARD = 50
    ADVERTISE_EXIT  = True

    def start (self):
        pass

    def parse (self, message):
        try:
            message.text    = unicodedata.normalize('NFKD', message.text.decode('ibm850')).encode('ascii','ignore')
        except Exception:
            pass
        
        tigi = BoardTigi.by_mobile(message.peer)
        if tigi:
            message.sender = tigi
        else:
            message.sender = None

    def handle (self, message):
        try: # message is credit from orangeml
            if message.transaction:
                transaction = Transaction.objects.get(id=message.transaction)
                tigi        = BoardTigi.by_mobile(transaction.mobile)
                tigi.credit+= transaction.amount
                tigi.save()
                transaction.delete()
                return True
        except AttributeError:
            pass

        try:
            func, captures = self.keyword.match(self, message.text)
        except TypeError:
            # didn't find a matching function
            # message.respond(_("Unknown or incorrectly formed command: %(msg)s... Please call 999-9999") % {"msg":message.text[:10]})
            return False
        try:
            handled = func(self, message, *captures)
        except HandlerFailed, e:
            message.respond(e.message)
            handled = True
        except Exception, e:
            message.respond(_(u"Une erreur s'est produite. Contactez le 73120896."))
            raise
        message.was_handled = bool(handled)
        return handled


    @keyword(r'new \@(\w+) (.+)')
    @authenticated
    def new_announce (self, message, zone, text):
        zone        = zone.lower()
        recipients  = self.recipients_from_zone(zone, message.peer)        
        self.group_send(message, recipients, _(u"Annonce (@%(sender)s): %(text)s") % {"text":text, 'sender':message.sender.name})
        self.followup_new_announce(message, recipients.__len__())
        return True

    def followup_new_announce(self, message, recipient_nb):
        price   = self.PRICE_PER_BOARD * int(recipient_nb)
        message.sender.credit    -= price
        message.sender.save()
        message.respond(_(u"Merci, votre annonce a été envoyée (%(price)dF). Il vous reste %(credit)sF de crédit.") % {'price':price, 'credit':message.sender.credit})

    @keyword(r'stop')
    @authenticated
    def stop_board (self, message):
        message.sender.active   = False
        message.sender.save()

        if self.ADVERTISE_EXIT:
            recipients  = []
            all_active  = BoardTigi.objects.filter(active=True)
            for board in all_active.iterator():
                recipients.append(board.mobile)
            self.group_send(message, recipients, _(u"Info: @%(sender)s a quitté le réseau.") % {'sender':message.sender.name})

        self.followup_stop_board(message, message.sender, recipients.__len__())
        return True

    def followup_stop_board(self, message, tigi, recipient_nb):
        price   = self.PRICE_PER_BOARD * int(recipient_nb)
        tigi.credit     -= price
        if tigi.credit < 0:
            tigi.credit = 0
        tigi.save()
        message.forward(tigi.mobile, _(u"Vous avez quitté le réseau. Votre crédit (si vous souhaitez revenir) est de %(credit)sF. Au revoir.") % {'credit':tigi.credit})

    @keyword(r'stop \@(\w+)')
    @sysadmin
    def stop_board (self, message, name):
        tigi    = BoardTigi.objects.get(name=name)
        if not tigi.active: # already off
            message.respond(_(u"@%(tigi)s ne fait pas partie du réseau.") % {'tigi':tigi.name})
            return True
        tigi.active   = False
        tigi.save()

        if self.ADVERTISE_EXIT:
            recipients  = []
            all_active  = BoardTigi.objects.filter(active=True)
            for board in all_active.iterator():
                recipients.append(board.mobile)
            self.group_send(message, recipients, _(u"Info: @%(sender)s a quitté le réseau.") % {'sender':tigi.name})

        self.followup_stop_board(message, tigi, recipients.__len__())
        return True

    def group_send(self, message, recipients, text):
        for number in recipients:
            message.forward(number, text)
        pass

    def recipients_from_zone(self, zone, exclude=None):     
        recipients  = []
        query_zone  = Zone.objects.get(name=zone)
        all_zones   = recurs_zones(query_zone)
        all_boards  = BoardTigi.objects.filter(zone__in=all_zones)

        for board in all_boards.iterator():
            recipients.append(board.mobile)

        if not exclude == None:
            recipients.remove(exclude)

        return recipients

    def outgoing (self, message):
        # if info message ; down tigi credit by 10F
        pass

