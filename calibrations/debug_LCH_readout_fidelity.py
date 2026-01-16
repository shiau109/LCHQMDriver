
# Single QUA script generated at 2025-12-19 10:24:02.671930
# QUA library version: 1.2.3


from qm import CompilerOptionArguments
from qm.qua import *

with program() as prog:
    v1 = declare(int, )
    v2 = declare(fixed, )
    v3 = declare(fixed, )
    v4 = declare(int, )
    a1 = declare(int, value=[0, 1])
    set_dc_offset("q1.z", "single", 0.0)
    align("q1.resonator", "q1.z", "q1.xy")
    align()
    with for_(v1,0,(v1<2000),(v1+1)):
        r1 = declare_stream()
        save(v1, r1)
        with for_each_((v4),(a1)):
            wait(344717, "q1.xy", "q1.resonator", "q1.z")
            align()
            align("q1.resonator", "q1.z", "q1.xy")
            with if_((v4==0)):
                pass
            with elif_((v4==1)):
                play("x180", "q1.xy")
            with elif_((v4==2)):
                pass
            align("q1.resonator", "q1.z", "q1.xy")
            measure("readout", "q1.resonator", dual_demod.full("iw1", "iw2", v2), dual_demod.full("iw3", "iw1", v3))
            align("q1.resonator", "q1.z", "q1.xy")
            r2 = declare_stream()
            save(v2, r2)
            r3 = declare_stream()
            save(v3, r3)
    with stream_processing():
        r1.save("n")
        r2.buffer(2).buffer(2000).save("I1")
        r3.buffer(2).buffer(2000).save("Q1")


####     SERIALIZATION WAS NOT COMPLETE     ####
#
#  Original   {  "script": {    "variables": [      {        "name": "v1",        "size": 1      },      {        "name": "v2",        "type": "REAL",        "size": 1      },      {        "name": "v3",        "type": "REAL",        "size": 1      },      {        "name": "v4",        "size": 1      },      {        "name": "a1",        "size": 2,        "value": [          {            "value": "0",            "loc": "stripped"          },          {            "value": "1",            "loc": "stripped"          }        ],        "dim": 1      }    ],    "body": {      "statements": [        {          "setDcOffset": {            "loc": "stripped",            "qe": {              "loc": "stripped",              "name": "q1.z"            },            "qeInputReference": "single",            "offset": {              "literal": {                "value": "0.0",                "type": "REAL",                "loc": "stripped"              }            }          }        },        {          "align": {            "loc": "stripped",            "qe": [              {                "loc": "stripped",                "name": "q1.resonator"              },              {                "loc": "stripped",                "name": "q1.z"              },              {                "loc": "stripped",                "name": "q1.xy"              }            ]          }        },        {          "align": {            "loc": "stripped"          }        },        {          "for": {            "init": {              "statements": [                {                  "assign": {                    "expression": {                      "literal": {                        "value": "0",                        "loc": "stripped"                      }                    },                    "target": {                      "variable": {                        "name": "v1",                        "loc": "stripped"                      }                    },                    "loc": "stripped"                  }                }              ]            },            "condition": {              "binaryOperation": {                "op": "LT",                "left": {                  "variable": {                    "name": "v1",                    "loc": "stripped"                  }                },                "right": {                  "literal": {                    "value": "2000",                    "loc": "stripped"                  }                },                "loc": "stripped"              }            },            "update": {              "statements": [                {                  "assign": {                    "expression": {                      "binaryOperation": {                        "left": {                          "variable": {                            "name": "v1",                            "loc": "stripped"                          }                        },                        "right": {                          "literal": {                            "value": "1",                            "loc": "stripped"                          }                        },                        "loc": "stripped"                      }                    },                    "target": {                      "variable": {                        "name": "v1",                        "loc": "stripped"                      }                    },                    "loc": "stripped"                  }                }              ]            },            "body": {              "statements": [                {                  "save": {                    "tag": "r0",                    "source": {                      "variable": {                        "name": "v1",                        "loc": "stripped"                      }                    },                    "loc": "stripped"                  }                },                {                  "forEach": {                    "iterator": [                      {                        "variable": {                          "name": "v4",                          "loc": "stripped"                        },                        "array": {                          "name": "a1",                          "loc": "stripped"                        }                      }                    ],                    "body": {                      "statements": [                        {                          "wait": {                            "loc": "stripped",                            "qe": [                              {                                "loc": "stripped",                                "name": "q1.xy"                              },                              {                                "loc": "stripped",                                "name": "q1.resonator"                              },                              {                                "loc": "stripped",                                "name": "q1.z"                              }                            ],                            "time": {                              "literal": {                                "value": "344717",                                "loc": "stripped"                              }                            }                          }                        },                        {                          "align": {                            "loc": "stripped"                          }                        },                        {                          "align": {                            "loc": "stripped",                            "qe": [                              {                                "loc": "stripped",                                "name": "q1.resonator"                              },                              {                                "loc": "stripped",                                "name": "q1.z"                              },                              {                                "loc": "stripped",                                "name": "q1.xy"                              }                            ]                          }                        },                        {                          "if": {                            "condition": {                              "binaryOperation": {                                "op": "EQ",                                "left": {                                  "variable": {                                    "name": "v4",                                    "loc": "stripped"                                  }                                },                                "right": {                                  "literal": {                                    "value": "0",                                    "loc": "stripped"                                  }                                },                                "loc": "stripped"                              }                            },                            "body": {},                            "else": {},                            "elseifs": [                              {                                "condition": {                                  "binaryOperation": {                                    "op": "EQ",                                    "left": {                                      "variable": {                                        "name": "v4",                                        "loc": "stripped"                                      }                                    },                                    "right": {                                      "literal": {                                        "value": "1",                                        "loc": "stripped"                                      }                                    },                                    "loc": "stripped"                                  }                                },                                "body": {                                  "statements": [                                    {                                      "play": {                                        "loc": "stripped",                                        "qe": {                                          "loc": "stripped",                                          "name": "q1.xy"                                        },                                        "namedPulse": {                                          "loc": "stripped",                                          "name": "x180"                                        }                                      }                                    }                                  ]                                },                                "loc": "stripped"                              },                              {                                "condition": {                                  "binaryOperation": {                                    "op": "EQ",                                    "left": {                                      "variable": {                                        "name": "v4",                                        "loc": "stripped"                                      }                                    },                                    "right": {                                      "literal": {                                        "value": "2",                                        "loc": "stripped"                                      }                                    },                                    "loc": "stripped"                                  }                                },                                "body": {},                                "loc": "stripped"                              }                            ],                            "loc": "stripped"                          }                        },                        {                          "align": {                            "loc": "stripped",                            "qe": [                              {                                "loc": "stripped",                                "name": "q1.resonator"                              },                              {                                "loc": "stripped",                                "name": "q1.z"                              },                              {                                "loc": "stripped",                                "name": "q1.xy"                              }                            ]                          }                        },                        {                          "measure": {                            "loc": "stripped",                            "qe": {                              "loc": "stripped",                              "name": "q1.resonator"                            },                            "pulse": {                              "loc": "stripped",                              "name": "readout"                            },                            "measureProcesses": [                              {                                "analog": {                                  "loc": "stripped",                                  "dualDemodIntegration": {                                    "integration1": {                                      "loc": "stripped",                                      "name": "iw1"                                    },                                    "integration2": {                                      "loc": "stripped",                                      "name": "iw2"                                    },                                    "target": {                                      "loc": "stripped",                                      "scalarProcess": {                                        "variable": {                                          "name": "v2",                                          "loc": "stripped"                                        }                                      }                                    },                                    "elementOutput1": "out1",                                    "elementOutput2": "out2"                                  }                                }                              },                              {                                "analog": {                                  "loc": "stripped",                                  "dualDemodIntegration": {                                    "integration1": {                                      "loc": "stripped",                                      "name": "iw3"                                    },                                    "integration2": {                                      "loc": "stripped",                                      "name": "iw1"                                    },                                    "target": {                                      "loc": "stripped",                                      "scalarProcess": {                                        "variable": {                                          "name": "v3",                                          "loc": "stripped"                                        }                                      }                                    },                                    "elementOutput1": "out1",                                    "elementOutput2": "out2"                                  }                                }                              }                            ]                          }                        },                        {                          "align": {                            "loc": "stripped",                            "qe": [                              {                                "loc": "stripped",                                "name": "q1.resonator"                              },                              {                                "loc": "stripped",                                "name": "q1.z"                              },                              {                                "loc": "stripped",                                "name": "q1.xy"                              }                            ]                          }                        },                        {                          "save": {                            "tag": "r1",                            "source": {                              "variable": {                                "name": "v2",                                "loc": "stripped"                              }                            },                            "loc": "stripped"                          }                        },                        {                          "save": {                            "tag": "r2",                            "source": {                              "variable": {                                "name": "v3",                                "loc": "stripped"                              }                            },                            "loc": "stripped"                          }                        }                      ]                    },                    "loc": "stripped"                  }                }              ]            },            "loc": "stripped"          }        }      ]    }  },  "resultAnalysis": {    "model": [      {        "values": [          {            "stringValue": "save"          },          {            "stringValue": "I1"          },          {            "listValue": {              "values": [                {                  "stringValue": "buffer"                },                {                  "stringValue": "2000"                },                {                  "listValue": {                    "values": [                      {                        "stringValue": "buffer"                      },                      {                        "stringValue": "2"                      },                      {                        "listValue": {                          "values": [                            {                              "stringValue": "@re"                            },                            {                              "stringValue": "0"                            },                            {                              "stringValue": "r1"                            }                          ]                        }                      }                    ]                  }                }              ]            }          }        ]      },      {        "values": [          {            "stringValue": "save"          },          {            "stringValue": "Q1"          },          {            "listValue": {              "values": [                {                  "stringValue": "buffer"                },                {                  "stringValue": "2000"                },                {                  "listValue": {                    "values": [                      {                        "stringValue": "buffer"                      },                      {                        "stringValue": "2"                      },                      {                        "listValue": {                          "values": [                            {                              "stringValue": "@re"                            },                            {                              "stringValue": "0"                            },                            {                              "stringValue": "r2"                            }                          ]                        }                      }                    ]                  }                }              ]            }          }        ]      },      {        "values": [          {            "stringValue": "save"          },          {            "stringValue": "n"          },          {            "listValue": {              "values": [                {                  "stringValue": "@re"                },                {                  "stringValue": "0"                },                {                  "stringValue": "r0"                }              ]            }          }        ]      }    ]  }}
#  Serialized {  "script": {    "variables": [      {        "name": "v1",        "size": 1      },      {        "name": "v2",        "type": "REAL",        "size": 1      },      {        "name": "v3",        "type": "REAL",        "size": 1      },      {        "name": "v4",        "size": 1      },      {        "name": "a1",        "size": 2,        "value": [          {            "value": "0",            "loc": "stripped"          },          {            "value": "1",            "loc": "stripped"          }        ],        "dim": 1      }    ],    "body": {      "statements": [        {          "setDcOffset": {            "loc": "stripped",            "qe": {              "loc": "stripped",              "name": "q1.z"            },            "qeInputReference": "single",            "offset": {              "literal": {                "value": "0.0",                "type": "REAL",                "loc": "stripped"              }            }          }        },        {          "align": {            "loc": "stripped",            "qe": [              {                "loc": "stripped",                "name": "q1.resonator"              },              {                "loc": "stripped",                "name": "q1.z"              },              {                "loc": "stripped",                "name": "q1.xy"              }            ]          }        },        {          "align": {            "loc": "stripped"          }        },        {          "for": {            "init": {              "statements": [                {                  "assign": {                    "expression": {                      "literal": {                        "value": "0",                        "loc": "stripped"                      }                    },                    "target": {                      "variable": {                        "name": "v1",                        "loc": "stripped"                      }                    },                    "loc": "stripped"                  }                }              ]            },            "condition": {              "binaryOperation": {                "op": "LT",                "left": {                  "variable": {                    "name": "v1",                    "loc": "stripped"                  }                },                "right": {                  "literal": {                    "value": "2000",                    "loc": "stripped"                  }                },                "loc": "stripped"              }            },            "update": {              "statements": [                {                  "assign": {                    "expression": {                      "binaryOperation": {                        "left": {                          "variable": {                            "name": "v1",                            "loc": "stripped"                          }                        },                        "right": {                          "literal": {                            "value": "1",                            "loc": "stripped"                          }                        },                        "loc": "stripped"                      }                    },                    "target": {                      "variable": {                        "name": "v1",                        "loc": "stripped"                      }                    },                    "loc": "stripped"                  }                }              ]            },            "body": {              "statements": [                {                  "save": {                    "tag": "r0",                    "source": {                      "variable": {                        "name": "v1",                        "loc": "stripped"                      }                    },                    "loc": "stripped"                  }                },                {                  "forEach": {                    "iterator": [                      {                        "variable": {                          "name": "v4",                          "loc": "stripped"                        },                        "array": {                          "name": "a1",                          "loc": "stripped"                        }                      }                    ],                    "body": {                      "statements": [                        {                          "wait": {                            "loc": "stripped",                            "qe": [                              {                                "loc": "stripped",                                "name": "q1.xy"                              },                              {                                "loc": "stripped",                                "name": "q1.resonator"                              },                              {                                "loc": "stripped",                                "name": "q1.z"                              }                            ],                            "time": {                              "literal": {                                "value": "344717",                                "loc": "stripped"                              }                            }                          }                        },                        {                          "align": {                            "loc": "stripped"                          }                        },                        {                          "align": {                            "loc": "stripped",                            "qe": [                              {                                "loc": "stripped",                                "name": "q1.resonator"                              },                              {                                "loc": "stripped",                                "name": "q1.z"                              },                              {                                "loc": "stripped",                                "name": "q1.xy"                              }                            ]                          }                        },                        {                          "if": {                            "condition": {                              "binaryOperation": {                                "op": "EQ",                                "left": {                                  "variable": {                                    "name": "v4",                                    "loc": "stripped"                                  }                                },                                "right": {                                  "literal": {                                    "value": "0",                                    "loc": "stripped"                                  }                                },                                "loc": "stripped"                              }                            },                            "body": {},                            "elseifs": [                              {                                "condition": {                                  "binaryOperation": {                                    "op": "EQ",                                    "left": {                                      "variable": {                                        "name": "v4",                                        "loc": "stripped"                                      }                                    },                                    "right": {                                      "literal": {                                        "value": "1",                                        "loc": "stripped"                                      }                                    },                                    "loc": "stripped"                                  }                                },                                "body": {                                  "statements": [                                    {                                      "play": {                                        "loc": "stripped",                                        "qe": {                                          "loc": "stripped",                                          "name": "q1.xy"                                        },                                        "namedPulse": {                                          "loc": "stripped",                                          "name": "x180"                                        }                                      }                                    }                                  ]                                },                                "loc": "stripped"                              },                              {                                "condition": {                                  "binaryOperation": {                                    "op": "EQ",                                    "left": {                                      "variable": {                                        "name": "v4",                                        "loc": "stripped"                                      }                                    },                                    "right": {                                      "literal": {                                        "value": "2",                                        "loc": "stripped"                                      }                                    },                                    "loc": "stripped"                                  }                                },                                "body": {},                                "loc": "stripped"                              }                            ],                            "loc": "stripped"                          }                        },                        {                          "align": {                            "loc": "stripped",                            "qe": [                              {                                "loc": "stripped",                                "name": "q1.resonator"                              },                              {                                "loc": "stripped",                                "name": "q1.z"                              },                              {                                "loc": "stripped",                                "name": "q1.xy"                              }                            ]                          }                        },                        {                          "measure": {                            "loc": "stripped",                            "qe": {                              "loc": "stripped",                              "name": "q1.resonator"                            },                            "pulse": {                              "loc": "stripped",                              "name": "readout"                            },                            "measureProcesses": [                              {                                "analog": {                                  "loc": "stripped",                                  "dualDemodIntegration": {                                    "integration1": {                                      "loc": "stripped",                                      "name": "iw1"                                    },                                    "integration2": {                                      "loc": "stripped",                                      "name": "iw2"                                    },                                    "target": {                                      "loc": "stripped",                                      "scalarProcess": {                                        "variable": {                                          "name": "v2",                                          "loc": "stripped"                                        }                                      }                                    },                                    "elementOutput1": "out1",                                    "elementOutput2": "out2"                                  }                                }                              },                              {                                "analog": {                                  "loc": "stripped",                                  "dualDemodIntegration": {                                    "integration1": {                                      "loc": "stripped",                                      "name": "iw3"                                    },                                    "integration2": {                                      "loc": "stripped",                                      "name": "iw1"                                    },                                    "target": {                                      "loc": "stripped",                                      "scalarProcess": {                                        "variable": {                                          "name": "v3",                                          "loc": "stripped"                                        }                                      }                                    },                                    "elementOutput1": "out1",                                    "elementOutput2": "out2"                                  }                                }                              }                            ]                          }                        },                        {                          "align": {                            "loc": "stripped",                            "qe": [                              {                                "loc": "stripped",                                "name": "q1.resonator"                              },                              {                                "loc": "stripped",                                "name": "q1.z"                              },                              {                                "loc": "stripped",                                "name": "q1.xy"                              }                            ]                          }                        },                        {                          "save": {                            "tag": "r1",                            "source": {                              "variable": {                                "name": "v2",                                "loc": "stripped"                              }                            },                            "loc": "stripped"                          }                        },                        {                          "save": {                            "tag": "r2",                            "source": {                              "variable": {                                "name": "v3",                                "loc": "stripped"                              }                            },                            "loc": "stripped"                          }                        }                      ]                    },                    "loc": "stripped"                  }                }              ]            },            "loc": "stripped"          }        }      ]    }  },  "resultAnalysis": {    "model": [      {        "values": [          {            "stringValue": "save"          },          {            "stringValue": "I1"          },          {            "listValue": {              "values": [                {                  "stringValue": "buffer"                },                {                  "stringValue": "2000"                },                {                  "listValue": {                    "values": [                      {                        "stringValue": "buffer"                      },                      {                        "stringValue": "2"                      },                      {                        "listValue": {                          "values": [                            {                              "stringValue": "@re"                            },                            {                              "stringValue": "0"                            },                            {                              "stringValue": "r1"                            }                          ]                        }                      }                    ]                  }                }              ]            }          }        ]      },      {        "values": [          {            "stringValue": "save"          },          {            "stringValue": "Q1"          },          {            "listValue": {              "values": [                {                  "stringValue": "buffer"                },                {                  "stringValue": "2000"                },                {                  "listValue": {                    "values": [                      {                        "stringValue": "buffer"                      },                      {                        "stringValue": "2"                      },                      {                        "listValue": {                          "values": [                            {                              "stringValue": "@re"                            },                            {                              "stringValue": "0"                            },                            {                              "stringValue": "r2"                            }                          ]                        }                      }                    ]                  }                }              ]            }          }        ]      },      {        "values": [          {            "stringValue": "save"          },          {            "stringValue": "n"          },          {            "listValue": {              "values": [                {                  "stringValue": "@re"                },                {                  "stringValue": "0"                },                {                  "stringValue": "r0"                }              ]            }          }        ]      }    ]  }}
#
################################################

        
config = {
    "version": 1,
    "controllers": {
        "con1": {
            "fems": {
                "2": {
                    "type": "LF",
                    "analog_outputs": {
                        "1": {
                            "delay": 0,
                            "shareable": False,
                            "sampling_rate": 1000000000.0,
                            "upsampling_mode": "pulse",
                            "output_mode": "direct",
                            "offset": 0.0,
                        },
                    },
                },
                "6": {
                    "type": "MW",
                    "analog_outputs": {
                        "8": {
                            "band": 1,
                            "delay": 0,
                            "shareable": False,
                            "sampling_rate": 1000000000.0,
                            "full_scale_power_dbm": -11,
                            "upconverter_frequency": 5000000000,
                        },
                        "7": {
                            "band": 1,
                            "delay": 0,
                            "shareable": False,
                            "sampling_rate": 1000000000.0,
                            "full_scale_power_dbm": 16,
                            "upconverter_frequency": 3150000000.0,
                        },
                    },
                    "analog_inputs": {
                        "2": {
                            "band": 1,
                            "downconverter_frequency": 5000000000,
                            "sampling_rate": 1000000000.0,
                            "shareable": False,
                        },
                    },
                },
            },
        },
    },
    "elements": {
        "q1.xy": {
            "operations": {
                "saturation": "q1.xy.saturation.pulse",
                "x180_DragCosine": "q1.xy.x180_DragCosine.pulse",
                "x90_DragCosine": "q1.xy.x90_DragCosine.pulse",
                "-x90_DragCosine": "q1.xy.-x90_DragCosine.pulse",
                "y180_DragCosine": "q1.xy.y180_DragCosine.pulse",
                "y90_DragCosine": "q1.xy.y90_DragCosine.pulse",
                "-y90_DragCosine": "q1.xy.-y90_DragCosine.pulse",
                "x180": "q1.xy.x180_DragCosine.pulse",
                "x90": "q1.xy.x90_DragCosine.pulse",
                "-x90": "q1.xy.-x90_DragCosine.pulse",
                "y180": "q1.xy.y180_DragCosine.pulse",
                "y90": "q1.xy.y90_DragCosine.pulse",
                "-y90": "q1.xy.-y90_DragCosine.pulse",
            },
            "intermediate_frequency": -72095999.0,
            "MWInput": {
                "port": ('con1', 6, 7),
                "upconverter": 1,
            },
        },
        "q1.resonator": {
            "operations": {
                "readout": "q1.resonator.readout.pulse",
                "saturation": "q1.resonator.saturation.pulse",
            },
            "intermediate_frequency": -87750000.0,
            "MWOutput": {
                "port": ('con1', 6, 2),
            },
            "smearing": 0,
            "time_of_flight": 384,
            "MWInput": {
                "port": ('con1', 6, 8),
                "upconverter": 1,
            },
        },
        "q1.z": {
            "operations": {
                "const": "q1.z.const.pulse",
            },
            "singleInput": {
                "port": ('con1', 2, 1),
            },
        },
    },
    "pulses": {
        "const_pulse": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "I": "const_wf",
                "Q": "zero_wf",
            },
        },
        "q1.xy.saturation.pulse": {
            "operation": "control",
            "length": 20000,
            "waveforms": {
                "I": "q1.xy.saturation.wf.I",
                "Q": "q1.xy.saturation.wf.Q",
            },
        },
        "q1.xy.x180_DragCosine.pulse": {
            "operation": "control",
            "length": 40,
            "waveforms": {
                "I": "q1.xy.x180_DragCosine.wf.I",
                "Q": "q1.xy.x180_DragCosine.wf.Q",
            },
        },
        "q1.xy.x90_DragCosine.pulse": {
            "operation": "control",
            "length": 40,
            "waveforms": {
                "I": "q1.xy.x90_DragCosine.wf.I",
                "Q": "q1.xy.x90_DragCosine.wf.Q",
            },
        },
        "q1.xy.-x90_DragCosine.pulse": {
            "operation": "control",
            "length": 40,
            "waveforms": {
                "I": "q1.xy.-x90_DragCosine.wf.I",
                "Q": "q1.xy.-x90_DragCosine.wf.Q",
            },
        },
        "q1.xy.y180_DragCosine.pulse": {
            "operation": "control",
            "length": 40,
            "waveforms": {
                "I": "q1.xy.y180_DragCosine.wf.I",
                "Q": "q1.xy.y180_DragCosine.wf.Q",
            },
        },
        "q1.xy.y90_DragCosine.pulse": {
            "operation": "control",
            "length": 40,
            "waveforms": {
                "I": "q1.xy.y90_DragCosine.wf.I",
                "Q": "q1.xy.y90_DragCosine.wf.Q",
            },
        },
        "q1.xy.-y90_DragCosine.pulse": {
            "operation": "control",
            "length": 40,
            "waveforms": {
                "I": "q1.xy.-y90_DragCosine.wf.I",
                "Q": "q1.xy.-y90_DragCosine.wf.Q",
            },
        },
        "q1.resonator.readout.pulse": {
            "operation": "measurement",
            "length": 4000,
            "digital_marker": "ON",
            "waveforms": {
                "I": "q1.resonator.readout.wf.I",
                "Q": "q1.resonator.readout.wf.Q",
            },
            "integration_weights": {
                "iw1": "q1.resonator.readout.iw1",
                "iw2": "q1.resonator.readout.iw2",
                "iw3": "q1.resonator.readout.iw3",
            },
        },
        "q1.resonator.saturation.pulse": {
            "operation": "measurement",
            "length": 4000,
            "digital_marker": "ON",
            "waveforms": {
                "I": "q1.resonator.saturation.wf.I",
                "Q": "q1.resonator.saturation.wf.Q",
            },
            "integration_weights": {
                "iw1": "q1.resonator.saturation.iw1",
                "iw2": "q1.resonator.saturation.iw2",
                "iw3": "q1.resonator.saturation.iw3",
            },
        },
        "q1.z.const.pulse": {
            "operation": "control",
            "length": 100,
            "waveforms": {
                "single": "q1.z.const.wf",
            },
        },
    },
    "waveforms": {
        "zero_wf": {
            "type": "constant",
            "sample": 0.0,
        },
        "const_wf": {
            "type": "constant",
            "sample": 0.1,
        },
        "q1.xy.saturation.wf.I": {
            "type": "constant",
            "sample": 0.34522422855726453,
        },
        "q1.xy.saturation.wf.Q": {
            "type": "constant",
            "sample": 0.0,
        },
        "q1.xy.x180_DragCosine.wf.I": {
            "type": "arbitrary",
            "samples": [0.0, 0.0022363153219334903, 0.008887341895578256, 0.019780821626300356, 0.03463461911115567, 0.05306402879762719, 0.07459173865535866, 0.09866019230702046, 0.12464602944561134, 0.15187623053897395, 0.17964554768215651, 0.2072347701477015, 0.23392935156570313, 0.25903791629945333, 0.2819101657112699, 0.3019537205556267, 0.3186494632904497, 0.3315649829487769, 0.340365774355668, 0.3448239016365274, 0.34482390163652743, 0.340365774355668, 0.33156498294877695, 0.31864946329044974, 0.30195372055562675, 0.2819101657112699, 0.2590379162994532, 0.23392935156570321, 0.20723477014770159, 0.17964554768215651, 0.1518762305389741, 0.12464602944561147, 0.09866019230702053, 0.07459173865535872, 0.053064028797627213, 0.03463461911115567, 0.01978082162630034, 0.008887341895578237, 0.0022363153219334903, 0.0],
        },
        "q1.xy.x180_DragCosine.wf.Q": {
            "type": "arbitrary",
            "samples": [0.0] * 40,
        },
        "q1.xy.x90_DragCosine.wf.I": {
            "type": "arbitrary",
            "samples": [0.0, 0.0011181576609667451, 0.004443670947789128, 0.009890410813150178, 0.017317309555577837, 0.026532014398813596, 0.03729586932767933, 0.04933009615351023, 0.06232301472280567, 0.07593811526948697, 0.08982277384107826, 0.10361738507385075, 0.11696467578285157, 0.12951895814972667, 0.14095508285563496, 0.15097686027781335, 0.15932473164522484, 0.16578249147438845, 0.170182887177834, 0.1724119508182637, 0.17241195081826372, 0.170182887177834, 0.16578249147438848, 0.15932473164522487, 0.15097686027781337, 0.14095508285563496, 0.1295189581497266, 0.11696467578285161, 0.10361738507385079, 0.08982277384107826, 0.07593811526948704, 0.062323014722805735, 0.049330096153510264, 0.03729586932767936, 0.026532014398813607, 0.017317309555577837, 0.00989041081315017, 0.004443670947789118, 0.0011181576609667451, 0.0],
        },
        "q1.xy.x90_DragCosine.wf.Q": {
            "type": "arbitrary",
            "samples": [0.0] * 40,
        },
        "q1.xy.-x90_DragCosine.wf.I": {
            "type": "arbitrary",
            "samples": [0.0, -0.0011181576609667451, -0.004443670947789128, -0.009890410813150178, -0.017317309555577837, -0.026532014398813596, -0.03729586932767933, -0.04933009615351023, -0.06232301472280567, -0.07593811526948697, -0.08982277384107826, -0.10361738507385075, -0.11696467578285157, -0.12951895814972667, -0.14095508285563496, -0.15097686027781335, -0.15932473164522484, -0.16578249147438845, -0.170182887177834, -0.1724119508182637, -0.17241195081826372, -0.170182887177834, -0.16578249147438848, -0.15932473164522487, -0.15097686027781337, -0.14095508285563496, -0.1295189581497266, -0.11696467578285161, -0.10361738507385079, -0.08982277384107826, -0.07593811526948704, -0.062323014722805735, -0.049330096153510264, -0.03729586932767936, -0.026532014398813607, -0.017317309555577837, -0.00989041081315017, -0.004443670947789118, -0.0011181576609667451, 0.0],
        },
        "q1.xy.-x90_DragCosine.wf.Q": {
            "type": "arbitrary",
            "samples": [0.0, 1.3693482004450158e-19, 5.441927402674041e-19, 1.2112259944576736e-18, 2.1207587717082272e-18, 3.2492346508438558e-18, 4.567426699356044e-18, 6.041194435602746e-18, 7.632368049349733e-18, 9.299736979805998e-18, 1.100011724750131e-17, 1.2689469896671006e-17, 1.4324041581077712e-17, 1.5861497752696275e-17, 1.7262019104270332e-17, 1.8489332868454128e-17, 1.9511652263433563e-17, 2.030249975387832e-17, 2.0841392805198956e-17, 2.111437437043375e-17, 2.1114374370433753e-17, 2.0841392805198956e-17, 2.0302499753878323e-17, 1.9511652263433566e-17, 1.848933286845413e-17, 1.7262019104270332e-17, 1.586149775269627e-17, 1.4324041581077715e-17, 1.268946989667101e-17, 1.100011724750131e-17, 9.299736979806005e-18, 7.63236804934974e-18, 6.041194435602751e-18, 4.567426699356047e-18, 3.249234650843857e-18, 2.1207587717082272e-18, 1.2112259944576726e-18, 5.441927402674029e-19, 1.3693482004450158e-19, 0.0],
        },
        "q1.xy.y180_DragCosine.wf.I": {
            "type": "arbitrary",
            "samples": [0.0, 1.3693482004450158e-19, 5.441927402674041e-19, 1.2112259944576736e-18, 2.1207587717082272e-18, 3.2492346508438558e-18, 4.567426699356044e-18, 6.041194435602746e-18, 7.632368049349733e-18, 9.299736979805998e-18, 1.100011724750131e-17, 1.2689469896671006e-17, 1.4324041581077712e-17, 1.5861497752696275e-17, 1.7262019104270332e-17, 1.8489332868454128e-17, 1.9511652263433563e-17, 2.030249975387832e-17, 2.0841392805198956e-17, 2.111437437043375e-17, 2.1114374370433753e-17, 2.0841392805198956e-17, 2.0302499753878323e-17, 1.9511652263433566e-17, 1.848933286845413e-17, 1.7262019104270332e-17, 1.586149775269627e-17, 1.4324041581077715e-17, 1.268946989667101e-17, 1.100011724750131e-17, 9.299736979806005e-18, 7.63236804934974e-18, 6.041194435602751e-18, 4.567426699356047e-18, 3.249234650843857e-18, 2.1207587717082272e-18, 1.2112259944576726e-18, 5.441927402674029e-19, 1.3693482004450158e-19, 0.0],
        },
        "q1.xy.y180_DragCosine.wf.Q": {
            "type": "arbitrary",
            "samples": [0.0, 0.0022363153219334903, 0.008887341895578256, 0.019780821626300356, 0.03463461911115567, 0.05306402879762719, 0.07459173865535866, 0.09866019230702046, 0.12464602944561134, 0.15187623053897395, 0.17964554768215651, 0.2072347701477015, 0.23392935156570313, 0.25903791629945333, 0.2819101657112699, 0.3019537205556267, 0.3186494632904497, 0.3315649829487769, 0.340365774355668, 0.3448239016365274, 0.34482390163652743, 0.340365774355668, 0.33156498294877695, 0.31864946329044974, 0.30195372055562675, 0.2819101657112699, 0.2590379162994532, 0.23392935156570321, 0.20723477014770159, 0.17964554768215651, 0.1518762305389741, 0.12464602944561147, 0.09866019230702053, 0.07459173865535872, 0.053064028797627213, 0.03463461911115567, 0.01978082162630034, 0.008887341895578237, 0.0022363153219334903, 0.0],
        },
        "q1.xy.y90_DragCosine.wf.I": {
            "type": "arbitrary",
            "samples": [0.0, 6.846741002225079e-20, 2.7209637013370203e-19, 6.056129972288368e-19, 1.0603793858541136e-18, 1.6246173254219279e-18, 2.283713349678022e-18, 3.020597217801373e-18, 3.8161840246748664e-18, 4.649868489902999e-18, 5.500058623750655e-18, 6.344734948335503e-18, 7.162020790538856e-18, 7.930748876348137e-18, 8.631009552135166e-18, 9.244666434227064e-18, 9.755826131716781e-18, 1.015124987693916e-17, 1.0420696402599478e-17, 1.0557187185216875e-17, 1.0557187185216877e-17, 1.0420696402599478e-17, 1.0151249876939162e-17, 9.755826131716783e-18, 9.244666434227066e-18, 8.631009552135166e-18, 7.930748876348134e-18, 7.162020790538857e-18, 6.344734948335505e-18, 5.500058623750655e-18, 4.649868489903003e-18, 3.81618402467487e-18, 3.0205972178013754e-18, 2.2837133496780236e-18, 1.6246173254219285e-18, 1.0603793858541136e-18, 6.056129972288363e-19, 2.7209637013370145e-19, 6.846741002225079e-20, 0.0],
        },
        "q1.xy.y90_DragCosine.wf.Q": {
            "type": "arbitrary",
            "samples": [0.0, 0.0011181576609667451, 0.004443670947789128, 0.009890410813150178, 0.017317309555577837, 0.026532014398813596, 0.03729586932767933, 0.04933009615351023, 0.06232301472280567, 0.07593811526948697, 0.08982277384107826, 0.10361738507385075, 0.11696467578285157, 0.12951895814972667, 0.14095508285563496, 0.15097686027781335, 0.15932473164522484, 0.16578249147438845, 0.170182887177834, 0.1724119508182637, 0.17241195081826372, 0.170182887177834, 0.16578249147438848, 0.15932473164522487, 0.15097686027781337, 0.14095508285563496, 0.1295189581497266, 0.11696467578285161, 0.10361738507385079, 0.08982277384107826, 0.07593811526948704, 0.062323014722805735, 0.049330096153510264, 0.03729586932767936, 0.026532014398813607, 0.017317309555577837, 0.00989041081315017, 0.004443670947789118, 0.0011181576609667451, 0.0],
        },
        "q1.xy.-y90_DragCosine.wf.I": {
            "type": "arbitrary",
            "samples": [0.0, 6.846741002225079e-20, 2.7209637013370203e-19, 6.056129972288368e-19, 1.0603793858541136e-18, 1.6246173254219279e-18, 2.283713349678022e-18, 3.020597217801373e-18, 3.8161840246748664e-18, 4.649868489902999e-18, 5.500058623750655e-18, 6.344734948335503e-18, 7.162020790538856e-18, 7.930748876348137e-18, 8.631009552135166e-18, 9.244666434227064e-18, 9.755826131716781e-18, 1.015124987693916e-17, 1.0420696402599478e-17, 1.0557187185216875e-17, 1.0557187185216877e-17, 1.0420696402599478e-17, 1.0151249876939162e-17, 9.755826131716783e-18, 9.244666434227066e-18, 8.631009552135166e-18, 7.930748876348134e-18, 7.162020790538857e-18, 6.344734948335505e-18, 5.500058623750655e-18, 4.649868489903003e-18, 3.81618402467487e-18, 3.0205972178013754e-18, 2.2837133496780236e-18, 1.6246173254219285e-18, 1.0603793858541136e-18, 6.056129972288363e-19, 2.7209637013370145e-19, 6.846741002225079e-20, 0.0],
        },
        "q1.xy.-y90_DragCosine.wf.Q": {
            "type": "arbitrary",
            "samples": [0.0, -0.0011181576609667451, -0.004443670947789128, -0.009890410813150178, -0.017317309555577837, -0.026532014398813596, -0.03729586932767933, -0.04933009615351023, -0.06232301472280567, -0.07593811526948697, -0.08982277384107826, -0.10361738507385075, -0.11696467578285157, -0.12951895814972667, -0.14095508285563496, -0.15097686027781335, -0.15932473164522484, -0.16578249147438845, -0.170182887177834, -0.1724119508182637, -0.17241195081826372, -0.170182887177834, -0.16578249147438848, -0.15932473164522487, -0.15097686027781337, -0.14095508285563496, -0.1295189581497266, -0.11696467578285161, -0.10361738507385079, -0.08982277384107826, -0.07593811526948704, -0.062323014722805735, -0.049330096153510264, -0.03729586932767936, -0.026532014398813607, -0.017317309555577837, -0.00989041081315017, -0.004443670947789118, -0.0011181576609667451, 0.0],
        },
        "q1.resonator.readout.wf.I": {
            "type": "constant",
            "sample": 0.027,
        },
        "q1.resonator.readout.wf.Q": {
            "type": "constant",
            "sample": 0.0,
        },
        "q1.resonator.saturation.wf.I": {
            "type": "constant",
            "sample": 0.054,
        },
        "q1.resonator.saturation.wf.Q": {
            "type": "constant",
            "sample": 0.0,
        },
        "q1.z.const.wf": {
            "type": "constant",
            "sample": 0.1,
        },
    },
    "digital_waveforms": {
        "ON": {
            "samples": [[1, 0]],
        },
    },
    "integration_weights": {
        "q1.resonator.readout.iw1": {
            "cosine": [(0.9304278434583189, 4000)],
            "sine": [(-0.36647513983557223, 4000)],
        },
        "q1.resonator.readout.iw2": {
            "cosine": [(0.36647513983557223, 4000)],
            "sine": [(0.9304278434583189, 4000)],
        },
        "q1.resonator.readout.iw3": {
            "cosine": [(-0.36647513983557223, 4000)],
            "sine": [(-0.9304278434583189, 4000)],
        },
        "q1.resonator.saturation.iw1": {
            "cosine": [(0.04554839574527009, 4000)],
            "sine": [(-0.9989621332388091, 4000)],
        },
        "q1.resonator.saturation.iw2": {
            "cosine": [(0.9989621332388091, 4000)],
            "sine": [(0.04554839574527009, 4000)],
        },
        "q1.resonator.saturation.iw3": {
            "cosine": [(-0.9989621332388091, 4000)],
            "sine": [(-0.04554839574527009, 4000)],
        },
    },
    "mixers": {},
    "oscillators": {},
}

loaded_config = None


