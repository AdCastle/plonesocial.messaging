# -*- coding: utf-8 -*-
import datetime
import json

from Products.Five.browser import BrowserView

from plone import api

from plone.z3cform.fieldsets import extensible
from z3c.form import button
from z3c.form import field
from z3c.form import form

from zope.component import getUtility
from zope.i18nmessageid import MessageFactory

from plonesocial.messaging.interfaces import IMessage
from plonesocial.messaging.interfaces import IMessagingLocator

_ = MessageFactory('plonesocial.microblog')


class MessageForm(extensible.ExtensibleForm, form.Form):

    ignoreContext = True  # don't use context to get widget data
    id = None
    label = _('Add a comment')
    fields = field.Fields(IMessage).select('recipient', 'text')

    def updateActions(self):
        super(MessageForm, self).updateActions()
        self.actions['send'].addClass('standalone')

    @button.buttonAndHandler(_(
        u'label_sendmessage',
        default=u'Send Message'),
        name='send')
    def handleMessage(self, action):

        # Validation form
        data, errors = self.extractData()
        if errors:
            return

        sender = api.user.get_current()
        recipient = api.user.get(username=data['recipient'])
        assert sender and recipient, 'nope'

        locator = getUtility(IMessagingLocator)
        inboxes = locator.get_inboxes()

        inboxes.send_message(sender.id, recipient.id, data['text'])

        # Redirect to portal home
        self.request.response.redirect(self.action)


class DateTimeJSONEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        else:
            return super(DateTimeJSONEncoder, self).default(obj)


class JsonView(BrowserView):

    def __init__(self, context, request):
        super(JsonView, self).__init__(context, request)
        self.request.response.setHeader('Content-type', 'application/json')

    def dumps(self, obj):
        return json.dumps(obj, indent=4, separators=(',', ': '),
                          cls=DateTimeJSONEncoder)

    def error(self, code, message):
        self.request.response.setStatus(code, reason=message)
        response = {'error': {'code': code,
                              'reason': message}}
        return self.dumps(response)

    def success(self, obj):
        return self.dumps(obj)


class MessagingView(JsonView):

    def inboxes(self):
        locator = getUtility(IMessagingLocator)
        return locator.get_inboxes()

    def messages(self):
        inboxes = self.inboxes()
        user = api.user.get_current()
        if user is None:
            return self.error(401, 'You need to log in to access the inbox')

        conversation_user_id = self.request.form.get('user')
        if conversation_user_id is None:
            return self.error(500, 'You need to provide a parameter "user"')

        if ((user.id not in inboxes or
             conversation_user_id not in inboxes[user.id])):
            messages = []
        else:
            conversation = inboxes[user.id][conversation_user_id]
            messages = [message.to_dict() for message in
                        conversation.get_messages()]

        result = {'messages': messages}
        return self.success(result)

    def delete_message(self):
        inboxes = self.inboxes()
        user = api.user.get_current()
        if user is None:
            return self.error(401, 'You need to log in to access the inbox')

        conversation_user_id = self.request.form.get('user')
        if conversation_user_id is None:
            return self.error(500, 'You need to provide a parameter "user"')

        message_id = self.request.form.get('message')
        if message_id is None:
            return self.error(500, 'You need to provide a parameter "message"')
        try:
            message_id = int(message_id)
        except ValueError:
            return self.error(500, 'message has to be an integer')
        result = False
        if user.id not in inboxes:
            msg = 'Inbox does not exist'
        elif conversation_user_id not in inboxes[user.id]:
            msg = 'Conversation does not exist'
        else:
            conversation = inboxes[user.id][conversation_user_id]
            if message_id not in conversation:
                msg = 'Message with id {id} does not exit'.format(
                    id=message_id)
            else:
                del conversation[message_id]
                result = True
                msg = 'Message {id} deleted'.format(id=message_id)
        return self.success({'result': result,
                             'message': msg})

    def conversations(self):
        inboxes = self.inboxes()
        user = api.user.get_current()
        if user is None:
            return self.error(401, 'You need to log in to access the inbox')

        if user.id not in inboxes:
            conversations = []
        else:
            conversations = [conversation.to_dict() for conversation in
                             inboxes[user.id].get_conversations()]

            result = {'conversations': conversations}
        return self.success(result)

    def delete_conversation(self):
        inboxes = self.inboxes()
        user = api.user.get_current()
        if user is None:
            return self.error(401, 'You need to log in to access the inbox')

        conversation_user_id = self.request.form.get('user')
        if conversation_user_id is None:
            return self.error(500, 'You need to provide a parameter "user"')

        if user.id not in inboxes:
            result = False
        elif conversation_user_id not in inboxes[user.id]:
            result = False
        else:
            del inboxes[user.id][conversation_user_id]
            result = True
        return self.success({'result': result})


class YourMessagesView(BrowserView):

    def your_messages(self):
        # count to show unread messages
        user = api.user.get_current()

        if user is None:
            # something has gone wrong
            return None
        if user.id == 'acl_users':
            # is anon
            return None

        locator = getUtility(IMessagingLocator)
        inboxes = locator.get_inboxes()

        if user.id not in inboxes:
            return None

        messages = inboxes[user.id]
        if not messages:
            return None

        return {'unread': messages.new_messages_count}
