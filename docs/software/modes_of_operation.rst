Modes of operation
==================

.. note::
   Mode ``grid`` is not implemented yet.

Systems with grid tie inverter
------------------------------

+--------------+--------------------+-------+----------+
| Mode         | Charger            | Solar | Inverter |
+==============+====================+=======+==========+
| charge       | on, full power     | on    | off      |
+--------------+--------------------+-------+----------+
| grid         | on, variable power | on    | off      |
+--------------+--------------------+-------+----------+
| idle         | off                | on    | off      |
+--------------+--------------------+-------+----------+
| discharge    | off                | on    | on       |
+--------------+--------------------+-------+----------+
| protect      | off                | off   | off      |
+--------------+--------------------+-------+----------+

Systems with hybrid inverter
----------------------------

+--------------+---------------------+----------------------+
| Mode         | Battery charged via | Output fed from      |
+==============+=====================+======================+
| charge       | solar + grid        | grid                 |
+--------------+---------------------+----------------------+
| grid         | solar               | grid                 |
+--------------+---------------------+----------------------+
| idle         | surplus solar       | solar + grid         |
+--------------+---------------------+----------------------+
| discharge    | surplus solar       | solar + battery      |
+--------------+---------------------+----------------------+
| protect      | none                | grid                 |
+--------------+---------------------+----------------------+

Using mode grid
---------------

Mode ``grid`` has different usecases depending on the system design.

For AC coupled battery storage systems or EV chargers, this mode is used to charge the battery from surplus grid energy.

For systems with hybrid inverters, this mode is useful to charge the battery from solar in winter during medium or low energy prices. Solar production in winter can usually not fully cover the energy demand of a home, but it would be economic to store the solar energy in the battery and use it when the energy prices are high.
