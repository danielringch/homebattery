[Solar] Victron Smart-/ BlueSolar MPPT
======================================

Driver name
-----------

victronMppt

Compatible devices
------------------

* Victron BlueSolar MPPT Series
* Victron SmartSolar MPPT Series

Tested devices
--------------

* Smartsolar MPPT 75/15

Remarks
-------

The :ref:`VE.Direct add-on board <handbook_ve_direct>` is necessary to connect the solar charger, communcation via Bluetooth is not supported.

The protocol is published by Victron, so there is high confidence that every model of the product family is working, despite not all have been tested yet.

Installation steps
------------------

* configure the TX pin of your charger to switch its charger output, see your device manual for more information
* connect the solar charger to the VE.Direct add-on board using an original VE.Direct cable
* edit the configuration as documented in :ref:`driver configuration <confiuration_victron_mppt>`