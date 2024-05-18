MQTT interface
==============

Homebattery uses MQTT as interface for integration.

Configuration
-------------

For configuration of MQTT, see the configuration page.

Topics
------

``<root>`` is set in the configuration.

``<live consumption topic>`` is set in the configuration

.. table::
   :widths: 1 1 1 10 50

   +------------------------------------+------------+-----------+-------------+--------------------------------------------------------------------------+
   | Topic                              | Datatype   | Direction | Unit        | Description                                                              |
   +====================================+============+===========+=============+==========================================================================+
   | ``<root>/mode/set``                | ``utf-8``  | W         | n.a.        | Requested operation mode. Possible values are ``charge``, ``discharge``, |
   |                                    |            |           |             | ``idle`` and ``protect``.                                                |
   +------------------------------------+------------+-----------+-------------+--------------------------------------------------------------------------+
   | ``<root>/mode/actual``             | ``utf-8``  | R         | n.a.        | Current operation mode. Possible values are ``charge``, ``discharge``,   |
   |                                    |            |           |             | ``idle`` and ``protect``.                                                |
   +------------------------------------+------------+-----------+-------------+--------------------------------------------------------------------------+
   | ``<live consumption topic>``       | ``uint16`` | W         | W           | Current energy live consumption.                                         |
   +------------------------------------+------------+-----------+-------------+--------------------------------------------------------------------------+
   | ``<root>/locked``                  | ``utf-8``  | R         | n.a.        | Reason for system lock. Only the reason with the highest priority is     |
   |                                    |            |           |             | sent. An empty payload means that there is no lock. For more             |
   |                                    |            |           |             | information about locks, see TODO.                                       |
   +------------------------------------+------------+-----------+-------------+--------------------------------------------------------------------------+
   | ``<root>/reset``                   | ``utf-8``  | W         | n.a.        | Writing the value "reset" to this topic will lead to a system reset.     |
   +------------------------------------+------------+-----------+-------------+--------------------------------------------------------------------------+
   | ``<root>/cha/state``               | ``int8``   | R         | n.a.        | Charger state. ``0`` means charger is off, ``1`` means charger is on,    |
   |                                    |            |           |             | ``-1`` means charger is in fault or syncing state.                       |
   +------------------------------------+------------+-----------+-------------+--------------------------------------------------------------------------+
   | ``<root>/cha/e``                   | ``uint16`` | R         | Wh          | Charger energy. Value is reset after every transmission.                 |
   +------------------------------------+------------+-----------+-------------+--------------------------------------------------------------------------+
   | ``<root>/inv/state``               | ``int8``   | R         | n.a.        | Inverter state. ``0`` means inverter is off, ``1`` means inverter is     |
   |                                    |            |           |             | on, ``-1`` means charger is in fault or syncing state.                   |
   +------------------------------------+------------+-----------+-------------+--------------------------------------------------------------------------+
   | ``<root>/inv/p``                   | ``uint16`` | R         | W           | Inverter power.                                                          |
   +------------------------------------+------------+-----------+-------------+--------------------------------------------------------------------------+
   | ``<root>/inv/e``                   | ``uint16`` | R         | Wh          | Inverter energy. Value is reset after every transmission.                |
   +------------------------------------+------------+-----------+-------------+--------------------------------------------------------------------------+
   | ``<root>/sol/state``               | ``int8``   | R         | n.a.        | Solar state. ``0`` means solar is off, ``1`` means solar is on,          |
   |                                    |            |           |             | ``-1`` means solar is in fault or syncing state.                         |
   +------------------------------------+------------+-----------+-------------+--------------------------------------------------------------------------+
   | ``<root>/sol/e``                   | ``uint16`` | R         | Wh          | Solar energy. Value is reset after every transmission.                   |
   +------------------------------------+------------+-----------+-------------+--------------------------------------------------------------------------+
   | ``<root>/bat/dev/<name>/v``        | ``uint16`` | R         | V / 100     | Battery voltage. ``<name>`` is the battery name set in the,              |
   |                                    |            |           |             | configuration.                                                           |
   +------------------------------------+------------+-----------+-------------+--------------------------------------------------------------------------+
   | ``<root>/bat/dev/<name>/i``        | ``int16``  | R         | A / 10      | Battery current. ``<name>`` is the battery name set in the,              |
   |                                    |            |           |             | configuration.                                                           |
   +------------------------------------+------------+-----------+-------------+--------------------------------------------------------------------------+
   | ``<root>/bat/dev/<name>/soc``      | ``uint8``  | R         | %           | Battery state of charge. ``<name>`` is the battery name set in the,      |
   |                                    |            |           |             | configuration.                                                           |
   +------------------------------------+------------+-----------+-------------+--------------------------------------------------------------------------+
   | ``<root>/bat/dev/<name>/c``        | ``uint16`` | R         | Ah / 10     | Battery remaining capacity. ``<name>`` is the battery name set in the,   |
   |                                    |            |           |             | configuration.                                                           |
   +------------------------------------+------------+-----------+-------------+--------------------------------------------------------------------------+
   | ``<root>/bat/dev/<name>/n``        | ``uint16`` | R         | -           | Battery cycles. ``<name>`` is the battery name set in the,               |
   |                                    |            |           |             | configuration.                                                           |
   +------------------------------------+------------+-----------+-------------+--------------------------------------------------------------------------+
   | ``<root>/bat/dev/<name>/temp/<n>`` | ``uint16`` | R         | °C / 10     | Battery cell temperature. ``<name>`` is the battery name set in the,     |
   |                                    |            |           |             | configuration, ``<n>`` is the sensor number.                             |
   +------------------------------------+------------+-----------+-------------+--------------------------------------------------------------------------+
   | ``<root>/bat/dev/<name>/cell/<n>`` | ``int16``  | R         | mV          | Battery cell voltage. ``<name>`` is the battery name set in the,         |
   |                                    |            |           |             | configuration, ``<n>`` is the cell number.                               |
   +------------------------------------+------------+-----------+-------------+--------------------------------------------------------------------------+
