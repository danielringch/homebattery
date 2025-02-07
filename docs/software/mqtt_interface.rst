MQTT interface
==============

Homebattery can be controlled and monitored over MQTT. Only MQTT v5 is supported.

For configuration of MQTT, see the :doc:`configuration page <configuration>`.

General messages
----------------

``<root>`` is the MQTT topic root set in the configuration.

+------------------------------------+------------+-----------+---------------------------------------------------------------------------+
| Topic                              | Datatype   | Direction | Description                                                               |
+====================================+============+===========+===========================================================================+
| ``<root>/mode/set``                | ``utf-8``  | W         | Requested operation mode.                                                 |
|                                    |            |           |                                                                           |
|                                    |            |           | Possible values are ``charge``, ``discharge``, ``idle`` and ``protect``.  |
+------------------------------------+------------+-----------+---------------------------------------------------------------------------+
| ``<root>/mode/actual``             | ``utf-8``  | R         | Current operation mode.                                                   |
|                                    |            |           |                                                                           |
|                                    |            |           | Possible values are ``charge``, ``discharge``, ``idle`` and ``protect``.  |
+------------------------------------+------------+-----------+---------------------------------------------------------------------------+
| ``<root>/locked``                  | ``utf-8``  | R         | Reason for system lock. Payload is JSON and contains a list of all locks. |
|                                    |            |           |                                                                           |
|                                    |            |           | An empty list means that there is no lock.                                |
+------------------------------------+------------+-----------+---------------------------------------------------------------------------+
| ``<root>/reset``                   | ``utf-8``  | W         | Writing the value ``reset`` to this topic will lead to a system reset.    |
+------------------------------------+------------+-----------+---------------------------------------------------------------------------+

Device class data
-----------------

For all device classes, two types of messages are sent:

* ``sum`` messages, containing aggregated measurement data of a whole device class
* ``dev`` messages, containing measurement data of a specific device

The device class ``sensor`` does not send ``sum`` messages.

All messages use a JSON payload:

.. code-block:: json

    {
        "capacity": "<float value, unit Ah>",
        "current": "<float value, unit A>",
        "energy": "<integer value, unit Wh>",
        "power": "<integer value, unit W>",
        "status": "<on / syncing / off / fault / offline>",
        "voltage": "<float value, unit V>"
    }

The content of a message may vary, not all measurands are present in every message.

``energy`` contains the energy since the last message containing an ``energy`` value, which means to get the energy of a longer period, the values of the ``energy`` messages need to be accumulated. All other measurands contain the average value since the last message with the same measurand. 

A measurand is sent with a minimum interval of ~ 6s when a value changed. In addition to that, it is sent every ~ 300s, even if no value changed. The device class ``battery`` sends messages every time the battery data is read, no matter whether a value changed or not.

Battery dev messages
~~~~~~~~~~~~~~~~~~~~

``battery`` ``dev`` messages use a different payload format:

.. code-block:: json

    {
        "v": "<battery voltage, float value, unit V>",
        "i": "<battery current, float value, unit A>",
        "soc": "<battery soc, float value, no unit>",
        "c": "<remaining capacity, float value, unit Ah>",
        "c_full": "<full battery capacity, float value, unit Ah>",
        "n": "<battery cycles, integer value, no unit>",
        "temps": "<battery cell temperatures, list of float values, unit °C>",
        "cells": "<battery cell voltage, list of float values, unit V>"
    }

Measurands are not sent if they are not supported by the battery.

Device class messages
---------------------

``<root>`` is the MQTT topic root set in the configuration.

``<name>`` is the device name set in the configuration.

+------------------------------------+------------+-----------+-------------------------------------------------------------------------------+
| Topic                              | Datatype   | Direction | Description                                                                   |
+====================================+============+===========+===============================================================================+
| ``<root>/cha/sum``                 | ``utf-8``  | R         | ``sum`` message of the ``charger`` device class.                              |
+------------------------------------+------------+-----------+-------------------------------------------------------------------------------+
| ``<root>/cha/dev/<name>``          | ``utf-8``  | R         | ``dev`` message of a ``charger`` device.                                      |
+------------------------------------+------------+-----------+-------------------------------------------------------------------------------+
| ``<root>/hea/sum``                 | ``utf-8``  | R         | ``sum`` message of the ``heater`` device class.                               |
+------------------------------------+------------+-----------+-------------------------------------------------------------------------------+
| ``<root>/hea/dev/<name>``          | ``utf-8``  | R         | ``dev`` message of a ``heater`` device.                                       |
+------------------------------------+------------+-----------+-------------------------------------------------------------------------------+
| ``<root>/inv/sum``                 | ``utf-8``  | R         | ``sum`` message of the ``inverter`` device class.                             |
+------------------------------------+------------+-----------+-------------------------------------------------------------------------------+
| ``<root>/inv/dev/<name>``          | ``utf-8``  | R         | ``dev`` message of a ``inverter`` device.                                     |
+------------------------------------+------------+-----------+-------------------------------------------------------------------------------+
| ``<root>/sol/sum``                 | ``utf-8``  | R         | ``sum`` message of the ``solar`` device class.                                |
+------------------------------------+------------+-----------+-------------------------------------------------------------------------------+
| ``<root>/sol/dev/<name>``          | ``utf-8``  | R         | ``dev`` message of a ``solar`` device.                                        |
+------------------------------------+------------+-----------+-------------------------------------------------------------------------------+
| ``<root>/bat/sum``                 | ``utf-8``  | R         | ``sum`` message of the ``battery`` device class.                              |
+------------------------------------+------------+-----------+-------------------------------------------------------------------------------+
| ``<root>/bat/dev/<name>``          | ``utf-8``  | R         | ``dev`` message of a ``battery`` device.                                      |
+------------------------------------+------------+-----------+-------------------------------------------------------------------------------+
| ``<root>/sen/dev/<name>``          | ``utf-8``  | R         | ``dev`` message of a ``sensor`` device.                                       |
+------------------------------------+------------+-----------+-------------------------------------------------------------------------------+
