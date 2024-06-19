System locks
============

Homebattery continuously monitors several parameters of the system and the connected devices to:

* prevent unsafe operation states
* prevent uneconomic operation

This is done by running checks. If a check fails, the affected device types are locked for activity.

There might be multiple locks active at the same time, but only the most critical one gets broadcasted via MQTT and is shown on the display.

The LEDs on the baseboard indicate whether a device type is locked or not.

.. note:: 
   Some checks can only be healed through a whole system reset. This can either be done by power cycling or triggering a reset over :doc:`MQTT <mqtt_interface>`.

Battery offline
---------------

**Check fails if** any battery was not successfully read within a time interval of ``treshold`` seconds.

**Check heals if** all batteries were successfully read within a time interval of ``treshold`` seconds.

**Objective**: operational safety

**Explanation**: Since the communication breakdown might be the sympton of malfunctioning battery management system, any use of the battery must be assumed to be unsafe.

**Locked devices**:

* all

Battery cell voltage low
------------------------

**Check fails if** any cell of any connected battery has a voltage below ``treshold`` volts.

**Check heals if** all cell voltages rise above (``treshold`` + ``hysteresis``) volts.

**Objective**: operational safety

**Explanation**: Discharging the battery would further might damage the battery.

**Locked devices**:

* inverter

**Remarks**: A too small value of ``hysteresis`` might cause the system to toggle between this check failing and not failing, since cell voltages change a bit when the battery current changes.

Battery cell voltage high
-------------------------

**Check fails if** any cell of any connected battery has a voltage above ``treshold`` volts.

**Check heals if** all cell voltages fall below (``treshold`` - ``hysteresis``) volts.

**Objective**: operational safety

**Explanation**: Charging the battery would further might damage the battery.

**Locked devices**:

* charger
* solar

**Remarks**: A too small value of ``hysteresis`` might cause the system to toggle between this check failing and not failing, since cell voltages change a bit when the battery current changes.

Battery temperature low for charging / discharging
--------------------------------------------------

**Check fails if** any cell temperature sensor of any connected battery has a temperature below ``treshold`` degrees celsius.

**Check heals if** all cell temperatures rise above (``treshold`` + ``hysteresis``) degrees celsius.

**Objective**: operational safety

**Explanation**: Charging or discharging the battery outside its safe temperature range might damage the battery.

**Locked devices**:

* charger (for charging)
* solar (for charge)
* inverter (for discharging)

**Remarks**: There are separate checks for charge and discharge, which can be configured independently from each other.

Battery temperature high for charging / discharging
---------------------------------------------------

**Check fails if** any cell temperature sensor of any connected battery has a temperature above ``treshold`` degrees celsius.

**Check heals if** all cell temperatures fall below (``treshold`` - ``hysteresis``) degrees celsius.

**Objective**: operational safety

**Explanation**: Charging or discharging the battery outside its safe temperature range might damage the battery.

**Locked devices**:

* charger (for charging)
* solar (for charge)
* inverter (for discharging)

**Remarks**: There are separate checks for charge and discharge, which can be configured independently from each other.

Live power consumption data lost for charging
---------------------------------------------

**Check fails if** no live power consumption data was received within a time interval of ``treshold`` seconds.

**Check heals if** live power consumption data was received within a time interval of ``treshold`` seconds.

**Objective**: economics

**Explanation**: When no live consumption data is reveiced from the power provider, the increased power consumption for charging might not be billed correctly.

**Locked devices**:

* charger

**Remarks**: 

This check is only useful if you:

* use dynamic electricity pricing
* get your live consumption data from your electricity provider (e.g. tibber) 

Live power consumption data lost for discharging
------------------------------------------------

**Check fails if** no live power consumption data was received within a time interval of ``treshold`` seconds.

**Check heals if** live power consumption data was received within a time interval of ``treshold`` seconds.

**Objective**: economics

**Explanation**: 

* the netzero algorithm does not work without live consumption data
* when no live consumption data is reveiced from the power provider, the decreased power consumption might not be billed correctly.

**Locked devices**:

* inverter

**Remarks**: 

This check is only useful if you:

* use netzero algorithm

or

* use dynamic electricity pricing
* get your live consumption data from your electricity provider (e.g. tibber) 

MQTT offline
------------

**Check fails if** the connection to the MQTT broker is interrupted.

**Check heals if** the connection to the MQTT broker is restored.

**Objective**: economics

**Explanation**: without a MQTT connection, homebattery can not be controlled anymore.

**Locked devices**:

* charger
* inverter

**Remarks**: if reconnecting fails, the whole system will reset.

Startup
-------

**Check fails if** any other lock is present during startup.

**Check heals if** no other locks are present or after 60 seconds.

**Objective**: operational safety

**Explanation**: before a connection to all devices is established, a safe operation of the system can not be guaranteed.

**Locked devices**:

* charger
* solar
* inverter

**Remarks**: this check can not be disabled.