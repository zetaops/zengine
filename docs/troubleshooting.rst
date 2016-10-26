.. highlight:: python
   :linenothreshold: 3

++++++++++++++++++++++++++++++++++++++++++++++++
Troubleshooting for Common Problems
++++++++++++++++++++++++++++++++++++++++++++++++

.. toctree::


Permission related
-------------------
- If you changed something and it doesn't take effect, try running the following command to clear your cache:

  ``redis-cli flushall``

Decorator usage
-------------------
- When you use a decorator from ``zengine.lib.decorators`` make sure the modules that contain decorated methods imported at runtime.
        - Module paths listed under ``settings.AUTO_IMPORT_MODULES`` are auto imported at runtime.
        - Modules that contain data model definitions are most likely imported by


  ``redis-cli flushall``


Pyoko / DB Related
-------------------
- Make sure you don't inadvertently add quotes around values in PyCharm's environmental variables:

    eg:

        ``DEFAULT_BUCKET_TYPE 'models'``

    Can cause something like following which is rather encryptic to debug for begginers:

    .. code-block:: bash

        RiakError: 'Expected status [200], received 404
        ~=QUERY DEBUG=~
        {\'QUERY\': \'-deleted:True\', \'BUCKET\': "\'models\'_personel",
        \'QUERY_PARAMS\': {\'sort\': b\'timestamp desc\', \'rows\': 1000}}'




