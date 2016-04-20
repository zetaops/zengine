.. highlight:: python
   :linenothreshold: 3

++++++++++++++++++++++++++++++++++++++++++++++++
Troubleshooting for Common Problems
++++++++++++++++++++++++++++++++++++++++++++++++

.. toctree::


Permission related
-------------------
- If you changed something and it doesn't take effect try:

  ``redis-cli flushall``


Pyoko / DB Related
-------------------
- Make sure you don't inadvertently add any quotes around values in PyCharm's environmental variables:
    eg:

        ``DEFAULT_BUCKET_TYPE 'models'``

    Can cause something like following which is rather encryptic to debug for begginers:

    .. code-block:: bash

        RiakError: 'Expected status [200], received 404
        ~=QUERY DEBUG=~
        {\'QUERY\': \'-deleted:True\', \'BUCKET\': "\'models\'_personel",
        \'QUERY_PARAMS\': {\'sort\': b\'timestamp desc\', \'rows\': 1000}}'




