#!/usr/bin/env python
"""
workflow worker daemon
"""
import pika

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
output_channel = connection.channel()
input_channel = connection.channel()

# output_channel.queue_declare(queue='hello')
input_channel.exchange_declare(exchange='tornado_input', type='direct')
result = input_channel.queue_declare(exclusive=True)
queue_name = result.method.queue
input_channel.queue_bind(exchange='tornado_input', queue=queue_name)


def callback(ch, method, properties, body):
    """
    this is a pika.basic_consumer callback
    handles client inputs, runs appropriate workflows

    Args:
        ch: amqp channel
        method: amqp method
        properties:
        body: message body
    """
    sessid = method.routing_key[3:]
    print("SESSID: %s" % sessid)
    output_channel.basic_publish(exchange='',
                                 routing_key=sessid,
                                 body='Hello %s, you said %s' % (sessid, body))

input_channel.basic_consume(callback,
                            queue='#',
                            no_ack=True)

input_channel.start_consuming()

