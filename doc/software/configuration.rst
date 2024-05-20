Configuration
=============

Configuration is done using a json file ``config.json``, which is uploaded onto the Raspberry Pi Pico, see TODO.


Example
-------

A template configuration file can be found in the repostiory in the `config folder <https://github.com/danielringch/homebattery/blob/main/config>`_ or can be found as part of every release.

Description
-----------

General
~~~~~~~

Parent key: ``general``

+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype, Unit | Description                                                                      | Recommended Value |
+========================+================+==================================================================================+===================+
| ``default_mode``       | string, -      | Mode of operation the system will switch to after startup when no mode request   | idle              |
|                        |                | is received in the meanwhile.                                                    |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``inverter_power``     | int, W         | | Inverter power when in operation mode discharge.                               | n.a.              |
|                        |                | | This valud is currently only used if netzero is disabled.                      |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

Network
~~~~~~~

Parent key: ``network``

+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype, Unit | Description                                                                      | Recommended Value |
+========================+================+==================================================================================+===================+
| ``ssid``               | string, -      | The SSID of your WLAN network.                                                   | n.a.              |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``password``           | string, -      | The password of your WLAN network.                                               | n.a.              |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``timeout``            | integer, s     | | The timeout for connecting to the network.                                     | 15                |
|                        |                | | If the system is not connected to the network after the timeout, the system    |                   |
|                        |                |   restarts.                                                                      |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``ntp_server``         | string, -      | Optional. The host address of the ntp server.                                    | time.google.com   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``timezone``           | integer, -     | | Optional. The UTC offset of your timezone.                                     | 1 for Berlin      |
|                        |                | | The UTC offsets can be found here:                                             |                   |
|                        |                |   https://en.wikipedia.org/wiki/List_of_UTC_offsets .                            |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``ntp_timeout``        | integer, s     | | Optional. The timeout for retriving time from the ntp server.                  | 10                |
|                        |                | | If no time was retrived from the ntp server after the timeout, the system      |                   |
|                        |                |   continues without time sync.                                                   |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

MQTT
~~~~

Parent key: ``mqtt``

+----------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| Key                        | Datatype | Description                                                                      | Recommended Value |
+============================+==========+==================================================================================+===================+
| ``host``                   | string   | Host address of the MQTT broker. Expected format is ``1.2.3.4:1883``.            | n.a.              |
+----------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| ``ca``                     | string   | Optional. File name of the TLS CA certificate.                                   | n.a.              |
+----------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| ``tls_insecure``           | boolean  | Optional. Turns on accepting self-signed TLS certificates.                       | n.a.              |
+----------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| ``user``                   | string   | Optional. Username for authentification at the MQTT broker.                      | n.a.              |
+----------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| ``password``               | string   | Optional. Password for authentification at the MQTT broker.                      | n.a.              |
+----------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| ``root``                   | string   | | MQTT root topic.                                                               | homebattery       | 
|                            |          | | All MQTT topics the system is using will be sub-topics of this root topic      |                   |
|                            |          |   (except for live energy consumption).                                          |                   |
+----------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| ``live_consumption_topic`` | string   | | MQTT topic where live energy consumption data is published.                    | n.a.              |
|                            |          | | The system will subscribe to this topic and will expect a 16 bit unsigned      |                   |
|                            |          |   integer value representing the current energy consumtion in watts.             |                   |
+----------------------------+----------+----------------------------------------------------------------------------------+-------------------+

Logging
~~~~~~~

Parent key: ``logging``

+------------------------+----------+-----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype | Description                                                                       | Recommended Value |
+========================+==========+===================================================================================+===================+
| ``host``               | string   | Optional.  If given, the logging data will be send via UDP to this host.          | n.a.              |
|                        |          | Expected format is ``1.2.3.4:1883.``                                              |                   |
+------------------------+----------+-----------------------------------------------------------------------------------+-------------------+
| ``ignore``             | list of  | | Logging sender that shall be ignored.                                           | mqtt, bluetooth   |
|                        | strings  | | Some parts of the system have a very verbose logging output for debug purposes. |                   |
|                        |          |   It can make sense to disable them in order to get a more readable log.          |                   |
+------------------------+----------+-----------------------------------------------------------------------------------+-------------------+

Netzero
~~~~~~~

Parent key: ``netzero``

+----------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                        | Datatype, Unit | Description                                                                      | Recommended Value |
+============================+================+==================================================================================+===================+
| ``enabled``                | boolean, -     | Enables the netzero algorithm.                                                   | n.a.              |
+----------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``evaluated_time_span``    | integer, s     | | Time span that will be evaluated, older data will be ignored.                  | 30                |
|                            |                | | The maximum value is 120.                                                      |                   |
+----------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``maturity_time_span``     | integer, s     | | Time span after an inverter power change during which netzero will not         | 15                |
|                            |                |   inverter power.                                                                |                   |
|                            |                | | Independently from this value, netzero will not change inverter power with     |                   |
|                            |                |   less than two data points.                                                     |                   |
+----------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``power_offset``           | integer, W     | Expected remaining minimum energy consumption.                                   | 10                |
+----------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``power_hysteresis``       | integer, W     | Hysteresis of the remaing minimum energy consumption.                            | 5                 |
+----------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``power_change_upwards``   | integer, W     | Maximum increase of the inverter power in a single inverter power change.        | 100 - 200         |
+----------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``power_change_downwards`` | integer, W     | Decrease of the inverter power in case of a backfeeding event.                   | 25 - 50           |
+----------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

Supervisor
~~~~~~~~~~~

Battery offline check
'''''''''''''''''''''

Parent key: ``supervisor``, ``battery_offline``

+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype, Unit | Description                                                                      | Recommended Value |
+========================+================+==================================================================================+===================+
| ``enabled``            | boolean, -     | Enables the check.                                                               | true              |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``threshold``          | integer, s     | | Maximum time span with no successful communication to any battery.             | 120               |
|                        |                | | Larger values lead to slower detection of malfunctioning battery BMS,          |                   |
|                        |                |   smaller values can lead to transient system locks.                             |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

Battery overcurrent check
'''''''''''''''''''''''''

Parent key: ``supervisor``, ``overcurrent``

+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype, Unit | Description                                                                      | Recommended Value |
+========================+================+==================================================================================+===================+
| ``enabled``            | boolean, -     | Enables the check.                                                               | true              |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

Battery offline check
'''''''''''''''''''''

Parent key: ``supervisor``, ``battery_offline``

+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype, Unit | Description                                                                      | Recommended Value |
+========================+================+==================================================================================+===================+
| ``enabled``            | boolean, -     | Enables the check.                                                               | true              |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``threshold``          | float, V       | | Maximum voltage of a battery cell.                                             | 3.65              |
|                        |                | | Larger values can lead to faster aging of battery cells, smaller values lead   |                   |
|                        |                |   to smaller usable battery capacity and can prevent cell balancing.             |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``hysteresis``         | float, V       | | Hysteresis of the threshold value.                                             | 0.25              |
|                        |                | | Larger values can prevent charing a partially discharged battery, smaller      |                   |
|                        |                |   values can lead to toggling between charging and non-charging state.           |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

Battery cell voltage low check
''''''''''''''''''''''''''''''

Parent key: ``supervisor``, ``cell_low``

+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype, Unit | Description                                                                      | Recommended Value |
+========================+================+==================================================================================+===================+
| ``enabled``            | boolean, -     | Enables the check.                                                               | true              |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``threshold``          | float, V       | | Minimum voltage of a battery cell.                                             | 3.1               |
|                        |                | | Larger values lead to smaller usable battery capacity, smaller values can lead |                   |
|                        |                |   to faster aging of battery cells.                                              |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``hysteresis``         | float, V       | | Hysteresis of the threshold value.                                             | 0.1               |
|                        |                | | Larger values can prevent discharing a partially charged battery, smaller      |                   |
|                        |                |   values can lead to toggling between discharging and non-discharging state.     |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

Battery cell temperature low while charging check
'''''''''''''''''''''''''''''''''''''''''''''''''

Parent key: ``supervisor``, ``temp_low_charge``

+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype, Unit | Description                                                                      | Recommended Value |
+========================+================+==================================================================================+===================+
| ``enabled``            | boolean, -     | Enables the check.                                                               | true              |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``threshold``          | float, °C      | | Minimum temperature of a battery.                                              | 10                |
|                        |                | | Larger values lead to smaller usable temperature range, smaller values can     |                   |
|                        |                |   lead to faster aging of battery cells.                                         |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``hysteresis``         | float, °C      | | Hysteresis of the threshold value.                                             | 2                 |
|                        |                | | Larger values lead to smaller usable temperature range, smaller values can     |                   |
|                        |                |   lead to toggling between charging and non-charging state.                      |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

Battery cell temperature low while discharging check
''''''''''''''''''''''''''''''''''''''''''''''''''''

Parent key: ``supervisor``, ``temp_low_discharge``

+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype, Unit | Description                                                                      | Recommended Value |
+========================+================+==================================================================================+===================+
| ``enabled``            | boolean, -     | Enables the check.                                                               | true              |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``threshold``          | float, °C      | | Minimum temperature of a battery.                                              | 0                 |
|                        |                | | Larger values lead to smaller usable temperature range, smaller values can     |                   |
|                        |                |   lead to faster aging of battery cells.                                         |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``hysteresis``         | float, °C      | | Hysteresis of the threshold value.                                             | 2                 |
|                        |                | | Larger values lead to smaller usable temperature range, smaller values can     |                   |
|                        |                |   lead to toggling between discharging and non-discharging state.                |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

Battery cell temperature high while charging check
''''''''''''''''''''''''''''''''''''''''''''''''''

Parent key: ``supervisor``, ``temp_high_charge``

+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype, Unit | Description                                                                      | Recommended Value |
+========================+================+==================================================================================+===================+
| ``enabled``            | boolean, -     | Enables the check.                                                               | true              |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``threshold``          | float, °C      | | Maximum temperature of a battery.                                              | 35                |
|                        |                | | Smaller values lead to smaller usable temperature range, higher values can     |                   |
|                        |                |   lead to faster aging of battery cells.                                         |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``hysteresis``         | float, °C      | | Hysteresis of the threshold value.                                             | 2                 |
|                        |                | | Larger values lead to smaller usable temperature range, smaller values can     |                   |
|                        |                |   lead to toggling between charging and non-charging state.                      |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

Battery cell temperature high while discharging check
'''''''''''''''''''''''''''''''''''''''''''''''''''''

Parent key: ``supervisor``, ``temp_high_discharge``

+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype, Unit | Description                                                                      | Recommended Value |
+========================+================+==================================================================================+===================+
| ``enabled``            | boolean, -     | Enables the check.                                                               | true              |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``threshold``          | float, °C      | | Maximum temperature of a battery.                                              | 35                |
|                        |                | | Smaller values lead to smaller usable temperature range, higher values can     |                   |
|                        |                |   lead to faster aging of battery cells.                                         |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``hysteresis``         | float, °C      | | Hysteresis of the threshold value.                                             | 2                 |
|                        |                | | Larger values lead to smaller usable temperature range, smaller values can     |                   |
|                        |                |   lead to toggling between discharging and non-discharging state.                |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

Live consumption data lost while charging check
'''''''''''''''''''''''''''''''''''''''''''''''

Parent key: ``supervisor``, ``live_data_lost_charge``

+-------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                     | Datatype, Unit | Description                                                                      | Recommended Value |
+=========================+================+==================================================================================+===================+
| ``enabled``             | boolean, -     | Enables the check.                                                               | true              |
+-------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``threshold``           | integer, s     | | Maximum time span without live consumption data in charge state.               | 300               |
|                         |                | | Larger values can lead to incorrect billing of the electricity consumption     |                   |
|                         |                |   used for charging, smaller values can lead to toggling between charging and    |                   |
|                         |                |   non-charging state.                                                            |                   |
+-------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

Live consumption data lost while discharging check
''''''''''''''''''''''''''''''''''''''''''''''''''

Parent key: ``supervisor``, ``live_data_lost_discharge``

+-------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                     | Datatype, Unit | Description                                                                      | Recommended Value |
+=========================+================+==================================================================================+===================+
| ``enabled``             | boolean, -     | Enables the check.                                                               | true              |
+-------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``threshold``           | integer, s     | | Maximum time span without live consumption data in discharge state.            | 60                |
|                         |                | | Larger values can lead to incorrect billing of the electricity consumption     |                   |
|                         |                |   reduced by the inverter and to inverter over- or underproduction, smaller      |                   |
|                         |                |   values can lead to toggling between discharging and non-discharging state.     |                   |
+-------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

MQTT offline check
''''''''''''''''''

Parent key: ``supervisor``, ``mqtt_offline``

+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype, Unit | Description                                                                      | Recommended Value |
+========================+================+==================================================================================+===================+
| ``enabled``            | boolean, -     | Enables the check.                                                               | true              |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``threshold``          | integer, s     | | Maximum time span without connection to the MQTT broker.                       | 60                |
|                        |                | | Larger values delay a system reset in case the connection can not be restored, |                   |
|                        |                |   smaller values may lead to unnecessary system resets.                          |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

Device drivers
~~~~~~~~~~~~~~

Parent key: ``devices``, ``<device name>``

``<device name>`` is used as display name and in MQTT topics. It must be unique.

+------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype | Description                                                                      | Recommended Value |
+========================+==========+==================================================================================+===================+
| ``driver``             | string   | Device driver. Values are given in the sub-sections below.                       | n.a.              |
+------------------------+----------+----------------------------------------------------------------------------------+-------------------+

LLT Power BMS with Bluetooth
''''''''''''''''''''''''''''

Driver name: ``lltPowerBmsV4Ble``

+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype, Unit | Description                                                                      | Recommended Value |
+========================+================+==================================================================================+===================+
| ``mac``                | string         | Bluetooth MAC address of the device. Expected format is ``aa:bb:cc:dd:ee:ff``.   | n.a.              |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

Daly H-Series Smart BMS with Bluetooth
''''''''''''''''''''''''''''''''''''''

Driver name: ``daly8S24V60A``

+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype, Unit | Description                                                                      | Recommended Value |
+========================+================+==================================================================================+===================+
| ``mac``                | string         | Bluetooth MAC address of the device. Expected format is ``aa:bb:cc:dd:ee:ff``.   | n.a.              |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

JK BMS BD4-Series
'''''''''''''''''

Driver name: ``jkBmsBd4``

+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype, Unit | Description                                                                      | Recommended Value |
+========================+================+==================================================================================+===================+
| ``mac``                | string         | Bluetooth MAC address of the device. Expected format is ``aa:bb:cc:dd:ee:ff``.   | n.a.              |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

MQTT battery
''''''''''''

Driver name: ``mqttBattery``

+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype, Unit | Description                                                                      | Recommended Value |
+========================+================+==================================================================================+===================+
| ``root_topic``         | string         | | MQTT root topic for the battery data sent from another homebattery controller. | n.a.              |
|                        |                | | Value has the following scheme: ``<root>/bat/dev/<name>``, where ``root`` is   |                   |
|                        |                |   the MQTT root topic of the other homebattery controller and ``name`` is the    |                   |
|                        |                |   device name of the battery.                                                    |                   |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``cells_count``        | int            | Number of cells of the battery.                                                  | n.a.              |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+
| ``temperature_count``  | int            | Number of temperature sensors of the battery.                                    | n.a.              |
+------------------------+----------------+----------------------------------------------------------------------------------+-------------------+

Victron SmartSolar MPPT / Victron BlueSolar MPPT
''''''''''''''''''''''''''''''''''''''''''''''''

Driver name: ``victronmppt``

+------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype | Description                                                                      | Recommended Value |
+========================+==========+==================================================================================+===================+
| ``port``               | string   | Expansion slot the addon board is connected to. Possible values are ``ext1``     | n.a.              |
|                        |          | and ``ext2``.                                                                    |                   |
+------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| ``power_hysteresis``   | integer  | Power hysteresis, power changes smaller than the hysteresis will be ignored.     | 2                 |
+------------------------+----------+----------------------------------------------------------------------------------+-------------------+

Shelly smart switch
'''''''''''''''''''

Driver name: ``shelly``

+------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype | Description                                                                      | Recommended Value |
+========================+==========+==================================================================================+===================+
| ``host``               | string   | Host address of the device. Expected format is ``1.2.3.4:80``                    | n.a.              |
+------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| ``relay_id``           | integer  | Relay id of the used output. Value is 0 for single switch models, 0 and 1 for    | n.a.              |
|                        |          | dual switch models.                                                              |                   |
+------------------------+----------+----------------------------------------------------------------------------------+-------------------+

AhoyDTU
'''''''

Driver name: ``ahoydtu``

+------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| Key                    | Datatype | Description                                                                      | Recommended Value |
+========================+==========+==================================================================================+===================+
| ``host``               | string   | Host address of the device. Expected format is ``1.2.3.4:80``                    | n.a.              |
+------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| ``id``                 | integer  | Id of the used inverter. Value can be taken from the AhoyDTU web interface start | n.a.              |
|                        |          | page.                                                                            |                   |
+------------------------+----------+----------------------------------------------------------------------------------+-------------------+
| ``power_lut``          | string   | Absolute path to the inverter power lookup table.                                | n.a.              |
+------------------------+----------+----------------------------------------------------------------------------------+-------------------+
