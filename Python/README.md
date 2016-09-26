# ViPR-Controller
Tools and projects related to API orchestration of ViPR Controller

vseLib is a set of python libraries used to encapsulate

app* are folders with utilities built on top of vseLib additions

Each utility has "-h". Executions generate local log folders, with records detailed at possibly 2 levels - output.txt will show what user saw on screen and log.txt will show full dump of debug data. Detail of onscreen output is controlled with mode option, and debugging output has 2 levels default and full (in full mode full text of API calls will be logged).

