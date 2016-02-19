#!/usr/bin/env python
import pika
import time

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()
channel2 = connection.channel()

channel.queue_declare(queue='hello')
channel2.queue_declare(queue='ehlo')


# print(" [x] Sent 'Hello World!'")
# connection.close()

def callback(ch, method, properties, body):
    print(body)
    time.sleep(1)
    channel.basic_publish(exchange='',
                          routing_key='hello',
                          body='Hello World!')


channel.basic_publish(exchange='',
                      routing_key='hello',
                      body='Hello World!')

channel2.basic_consume(callback,
                      queue='ehlo',
                      no_ack=True)

channel2.start_consuming()

