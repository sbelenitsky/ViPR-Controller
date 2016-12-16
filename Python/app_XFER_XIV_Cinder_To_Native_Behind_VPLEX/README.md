Utility is under testing.

Purpose is to be able to remove Cinder controller from control path in ViPR 3.5, after Cinder was used to manage now supported storage array behind VPLEX.

In this particular example, ViPR C 3.0 was installed with VPLEX/XIV, and Cinder used to control XIV to VPLEX management path. 

We want to remove Cinder nodes from ViPR and update information in ViPR DB to reflect as if it was natively provisioned.


There is a missing "satellite" file with data directly pulled from XIV - but sample file contains customer data so can't post. It essentially specifies names and native IDs of XIV's export masks and volumes.