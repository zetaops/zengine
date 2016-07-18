# -*-  coding: utf-8 -*-
"""
When a user is not online, AMQP messages that sent to this
user are discarded at users private exchange.
When user come back, offline sent messages will be loaded
from DB and send to users private exchange.

Because of this, we need to fully simulate 2 online users to test real time chat behaviour.

"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
import uuid

import pika
from tornado.escape import json_encode, json_decode

from zengine.current import Current
from zengine.lib.cache import Session
from zengine.log import log
from zengine.tornado_server.ws_to_queue import QueueManager, NON_BLOCKING_MQ_PARAMS
import sys

from zengine.views.auth import Login

sys.sessid_to_userid = {}
from ulakbus.models import User

class TestQueueManager(QueueManager):

    def on_input_queue_declare(self, queue):
        """
        AMQP connection callback.
        Creates input channel.

        Args:
            connection: AMQP connection
        """
        log.info("input queue declared")
        super(TestQueueManager, self).on_input_queue_declare(queue)
        self.run_after_connection()

    # def connect(self):
    #     """
    #     Creates connection to RabbitMQ server
    #     """
    #     if self.connecting:
    #         log.info('PikaClient: Already connecting to RabbitMQ')
    #         return
    #
    #     log.info('PikaClient: Connecting to RabbitMQ')
    #     self.connecting = True
    #     self.connection = pika.LibevConnection(NON_BLOCKING_MQ_PARAMS,
    #                                            on_open_error_callback=self.conn_err,
    #                                            on_open_callback=self.on_connected)
    #     print(self.connection.is_open)

    def __init__(self, *args, **kwargs):
        super(TestQueueManager, self).__init__(*args, **kwargs)
        log.info("queue manager init")
        self.test_class = lambda qm: 1

    def conn_err(self, *args, **kwargs):
        log("conne err: %s %s" % (args, kwargs))



    def run_after_connection(self):
        log.info("run after connect")
        self.test_class(self)

    def set_test_class(self, kls):
        log.info("test class setted %s" % kls)
        self.test_class = kls


class TestWebSocket(object):
    def __init__(self, queue_manager, username, sess_id=None):
        self.message_callbacks = {}
        self.message_stack = {}
        self.user = User.objects.get(username=username)

        self.request = type('MockWSRequestObject', (object,), {'remote_ip': '127.0.0.1'})
        self.queue_manager = queue_manager
        self.sess_id = sess_id or uuid.uuid4().hex
        sys.sessid_to_userid[self.sess_id] = self.user.key.lower()
        self.queue_manager.register_websocket(self.sess_id, self)
        self.login_user()
        # mimic tornado ws object
        # zengine.tornado_server.ws_to_queue.QueueManager will call write_message() method
        self.write_message = self.backend_to_client

    def login_user(self):
        session = Session(self.sess_id)
        current = Current(session=session, input={})
        current.auth.set_user(self.user)
        Login(current)._do_upgrade()

    def backend_to_client(self, body):
        """
        from backend to client
        """
        body = json_decode(body)
        try:
            self.message_callbacks[body['callbackID']](body)
        except KeyError:
            self.message_stack[body['callbackID']] = body
        log.info("WRITE MESSAGE TO CLIENT:\n%s" % (body,))

    def client_to_backend(self, message, callback):
        """
        from client to backend
        """
        cbid = uuid.uuid4().hex
        self.message_callbacks[cbid] = callback
        message = json_encode({"callbackID": cbid, "data": message})
        log.info("GOT MESSAGE FOR BACKEND %s: %s" % (self.sess_id, message))
        self.queue_manager.redirect_incoming_message(self.sess_id, message, self.request)


class ConcurrentTestCase(object):
    def __init__(self, queue_manager):
        log.info("ConcurrentTestCase class init with %s" % queue_manager)
        self.queue_manager = queue_manager

        self.ws1 = TestWebSocket(self.queue_manager, 'ulakbus')
        self.ws2 = TestWebSocket(self.queue_manager, 'ogrenci_isleri_1')
        self.run_tests()

    def run_tests(self):
        for name in sorted(self.__class__.__dict__):
            if name.startswith("test_"):
                try:
                    getattr(self, name)()
                    print("%s succesfully passed" % name)
                except:
                    print("%s FAIL" % name)

    def success_test_callback(self, response, request=None):
        # print(response)
        assert response['code'] in (200, 201), "Process response not successful: \n %s \n %s" % (
            response, request
        )

    def test_channel_list(self):
        self.ws1.client_to_backend({"view": "_zops_list_channels"},
                                   self.success_test_callback)

    def test_search_user(self):
        self.ws1.client_to_backend({"view": "_zops_search_user",
                                    "query":"x"},
                                   self.success_test_callback)


class AMQPLoop(object):
    """This is an example consumer that will handle unexpected interactions
    with RabbitMQ such as channel and connection closures.

    If RabbitMQ closes the connection, it will reopen it. You should
    look at the output, as there are limited reasons why the connection may
    be closed, which usually are tied to permission related issues or
    socket timeouts.

    If the channel is closed, it will indicate a problem with one of the
    commands that were issued and that should surface in the output as well.

    """
    EXCHANGE = 'message'
    EXCHANGE_TYPE = 'topic'
    QUEUE = 'text'
    ROUTING_KEY = 'example.text'

    def __init__(self, amqp_url):
        """Create a new instance of the consumer class, passing in the AMQP
        URL used to connect to RabbitMQ.

        :param str amqp_url: The AMQP url to connect with

        """
        self._connection = None
        self._channel = None
        self._closing = False
        self._consumer_tag = None
        self._url = amqp_url

    def connect(self):
        """This method connects to RabbitMQ, returning the connection handle.
        When the connection is established, the on_connection_open method
        will be invoked by pika.

        :rtype: pika.SelectConnection

        """
        log.info('Connecting to %s', self._url)
        return pika.SelectConnection(pika.URLParameters(self._url),
                                     self.on_connection_open,
                                     stop_ioloop_on_close=False)

    def on_connection_open(self, unused_connection):
        """This method is called by pika once the connection to RabbitMQ has
        been established. It passes the handle to the connection object in
        case we need it, but in this case, we'll just mark it unused.

        :type unused_connection: pika.SelectConnection

        """
        log.info('Connection opened')
        self.add_on_connection_close_callback()
        self.open_channel()

    def add_on_connection_close_callback(self):
        """This method adds an on close callback that will be invoked by pika
        when RabbitMQ closes the connection to the publisher unexpectedly.

        """
        log.info('Adding connection close callback')
        self._connection.add_on_close_callback(self.on_connection_closed)

    def on_connection_closed(self, connection, reply_code, reply_text):
        """This method is invoked by pika when the connection to RabbitMQ is
        closed unexpectedly. Since it is unexpected, we will reconnect to
        RabbitMQ if it disconnects.

        :param pika.connection.Connection connection: The closed connection obj
        :param int reply_code: The server provided reply_code if given
        :param str reply_text: The server provided reply_text if given

        """
        self._channel = None
        if self._closing:
            self._connection.ioloop.stop()
        else:
            log.warning('Connection closed, reopening in 5 seconds: (%s) %s',
                        reply_code, reply_text)
            self._connection.add_timeout(5, self.reconnect)

    def reconnect(self):
        """Will be invoked by the IOLoop timer if the connection is
        closed. See the on_connection_closed method.

        """
        # This is the old connection IOLoop instance, stop its ioloop
        self._connection.ioloop.stop()

        if not self._closing:
            # Create a new connection
            self._connection = self.connect()

            # There is now a new connection, needs a new ioloop to run
            self._connection.ioloop.start()

    def open_channel(self):
        """Open a new channel with RabbitMQ by issuing the Channel.Open RPC
        command. When RabbitMQ responds that the channel is open, the
        on_channel_open callback will be invoked by pika.

        """
        log.info('Creating a new channel')
        self._connection.channel(on_open_callback=self.on_channel_open)

    def on_channel_open(self, channel):
        """This method is invoked by pika when the channel has been opened.
        The channel object is passed in so we can make use of it.

        Since the channel is now open, we'll declare the exchange to use.

        :param pika.channel.Channel channel: The channel object

        """
        log.info('Channel opened')
        self._channel = channel
        self.add_on_channel_close_callback()
        self.setup_exchange(self.EXCHANGE)

    def add_on_channel_close_callback(self):
        """This method tells pika to call the on_channel_closed method if
        RabbitMQ unexpectedly closes the channel.

        """
        log.info('Adding channel close callback')
        self._channel.add_on_close_callback(self.on_channel_closed)

    def on_channel_closed(self, channel, reply_code, reply_text):
        """Invoked by pika when RabbitMQ unexpectedly closes the channel.
        Channels are usually closed if you attempt to do something that
        violates the protocol, such as re-declare an exchange or queue with
        different parameters. In this case, we'll close the connection
        to shutdown the object.

        :param pika.channel.Channel: The closed channel
        :param int reply_code: The numeric reason the channel was closed
        :param str reply_text: The text reason the channel was closed

        """
        log.warning('Channel %i was closed: (%s) %s',
                    channel, reply_code, reply_text)
        self._connection.close()

    def setup_exchange(self, exchange_name):
        """Setup the exchange on RabbitMQ by invoking the Exchange.Declare RPC
        command. When it is complete, the on_exchange_declareok method will
        be invoked by pika.

        :param str|unicode exchange_name: The name of the exchange to declare

        """
        log.info('Declaring exchange %s', exchange_name)
        self._channel.exchange_declare(self.on_exchange_declareok,
                                       exchange_name,
                                       self.EXCHANGE_TYPE)

    def on_exchange_declareok(self, unused_frame):
        """Invoked by pika when RabbitMQ has finished the Exchange.Declare RPC
        command.

        :param pika.Frame.Method unused_frame: Exchange.DeclareOk response frame

        """
        log.info('Exchange declared')
        self.setup_queue(self.QUEUE)

    def setup_queue(self, queue_name):
        """Setup the queue on RabbitMQ by invoking the Queue.Declare RPC
        command. When it is complete, the on_queue_declareok method will
        be invoked by pika.

        :param str|unicode queue_name: The name of the queue to declare.

        """
        log.info('Declaring queue %s', queue_name)
        self._channel.queue_declare(self.on_queue_declareok, queue_name)

    def on_queue_declareok(self, method_frame):
        """Method invoked by pika when the Queue.Declare RPC call made in
        setup_queue has completed. In this method we will bind the queue
        and exchange together with the routing key by issuing the Queue.Bind
        RPC command. When this command is complete, the on_bindok method will
        be invoked by pika.

        :param pika.frame.Method method_frame: The Queue.DeclareOk frame

        """
        log.info('Binding %s to %s with %s',
                 self.EXCHANGE, self.QUEUE, self.ROUTING_KEY)
        self._channel.queue_bind(self.on_bindok, self.QUEUE,
                                 self.EXCHANGE, self.ROUTING_KEY)

    def on_bindok(self, unused_frame):
        """Invoked by pika when the Queue.Bind method has completed. At this
        point we will start consuming messages by calling start_consuming
        which will invoke the needed RPC commands to start the process.

        :param pika.frame.Method unused_frame: The Queue.BindOk response frame

        """
        log.info('Queue bound')
        self.start_consuming()

    def start_consuming(self):
        """This method sets up the consumer by first calling
        add_on_cancel_callback so that the object is notified if RabbitMQ
        cancels the consumer. It then issues the Basic.Consume RPC command
        which returns the consumer tag that is used to uniquely identify the
        consumer with RabbitMQ. We keep the value to use it when we want to
        cancel consuming. The on_message method is passed in as a callback pika
        will invoke when a message is fully received.

        """
        log.info('Issuing consumer related RPC commands')
        self.add_on_cancel_callback()
        self._consumer_tag = self._channel.basic_consume(self.on_message,
                                                         self.QUEUE)

    def add_on_cancel_callback(self):
        """Add a callback that will be invoked if RabbitMQ cancels the consumer
        for some reason. If RabbitMQ does cancel the consumer,
        on_consumer_cancelled will be invoked by pika.

        """
        log.info('Adding consumer cancellation callback')
        self._channel.add_on_cancel_callback(self.on_consumer_cancelled)

    def on_consumer_cancelled(self, method_frame):
        """Invoked by pika when RabbitMQ sends a Basic.Cancel for a consumer
        receiving messages.

        :param pika.frame.Method method_frame: The Basic.Cancel frame

        """
        log.info('Consumer was cancelled remotely, shutting down: %r',
                 method_frame)
        if self._channel:
            self._channel.close()

    def on_message(self, unused_channel, basic_deliver, properties, body):
        """Invoked by pika when a message is delivered from RabbitMQ. The
        channel is passed for your convenience. The basic_deliver object that
        is passed in carries the exchange, routing key, delivery tag and
        a redelivered flag for the message. The properties passed in is an
        instance of BasicProperties with the message properties and the body
        is the message that was sent.

        :param pika.channel.Channel unused_channel: The channel object
        :param pika.Spec.Basic.Deliver: basic_deliver method
        :param pika.Spec.BasicProperties: properties
        :param str|unicode body: The message body

        """
        log.info('Received message # %s from %s: %s',
                 basic_deliver.delivery_tag, properties.app_id, body)
        self.acknowledge_message(basic_deliver.delivery_tag)

    def acknowledge_message(self, delivery_tag):
        """Acknowledge the message delivery from RabbitMQ by sending a
        Basic.Ack RPC method for the delivery tag.

        :param int delivery_tag: The delivery tag from the Basic.Deliver frame

        """
        log.info('Acknowledging message %s', delivery_tag)
        self._channel.basic_ack(delivery_tag)

    def stop_consuming(self):
        """Tell RabbitMQ that you would like to stop consuming by sending the
        Basic.Cancel RPC command.

        """
        if self._channel:
            log.info('Sending a Basic.Cancel RPC command to RabbitMQ')
            self._channel.basic_cancel(self.on_cancelok, self._consumer_tag)

    def on_cancelok(self, unused_frame):
        """This method is invoked by pika when RabbitMQ acknowledges the
        cancellation of a consumer. At this point we will close the channel.
        This will invoke the on_channel_closed method once the channel has been
        closed, which will in-turn close the connection.

        :param pika.frame.Method unused_frame: The Basic.CancelOk frame

        """
        log.info('RabbitMQ acknowledged the cancellation of the consumer')
        self.close_channel()

    def close_channel(self):
        """Call to close the channel with RabbitMQ cleanly by issuing the
        Channel.Close RPC command.

        """
        log.info('Closing the channel')
        self._channel.close()

    def run(self):
        """Run the example consumer by connecting to RabbitMQ and then
        starting the IOLoop to block and allow the SelectConnection to operate.

        """
        self._connection = self.connect()
        self._connection.ioloop.start()

    def stop(self):
        """Cleanly shutdown the connection to RabbitMQ by stopping the consumer
        with RabbitMQ. When RabbitMQ confirms the cancellation, on_cancelok
        will be invoked by pika, which will then closing the channel and
        connection. The IOLoop is started again because this method is invoked
        when CTRL-C is pressed raising a KeyboardInterrupt exception. This
        exception stops the IOLoop which needs to be running for pika to
        communicate with RabbitMQ. All of the commands issued prior to starting
        the IOLoop will be buffered but not processed.

        """
        log.info('Stopping')
        self._closing = True
        self.stop_consuming()
        self._connection.ioloop.start()
        log.info('Stopped')

    def close_connection(self):
        """This method closes the connection to RabbitMQ."""
        log.info('Closing connection')
        self._connection.close()


def main():
    from tornado import ioloop
    # initiate amqp manager
    ioloop = ioloop.IOLoop.instance()
    qm = TestQueueManager(io_loop=ioloop)

    # initiate test case
    qm.set_test_class(ConcurrentTestCase)

    qm.connect()
    ioloop.start()


if __name__ == '__main__':
    main()
