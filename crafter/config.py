import argparse
import os
import numpy as np 

def str2bool(v):
  return v.lower() in ('true', '1')

arg_lists = []
# parser = argparse.ArgumentParser()

def add_argument_group(name):
  arg = parser.add_argument_group(name)
  arg_lists.append(arg)
  return arg

	
#buildActionList: actions for the beer game problem	
def buildActionList(config):
	aDiv = 1  # difference in the action list
	if config.fixedAction:
		actions = list(range(0,config.actionMax+1,aDiv)) # If you put the second argument =11, creates an actionlist from 0..xx
	else:
		actions = list(range(config.actionLow,config.actionUp+1,aDiv) )
	return actions	
	
# specify the dimension of the state of the game	
def getStateDim(config):
	if config.ifUseASAO:
		stateDim=5
	else:
		stateDim=3

	if config.ifUseActionInD:
		stateDim += 1

	return stateDim	

# agents 1=[dnn,dnn,dnn,dnn]; 2=[dnn,Strm,Strm,Strm]; 3=[dnn,bs,bs,bs]
def setAgentType(config):
	if config.gameConfig == 1:   # all agents are run by DNN- Also, load-model loads from brain-3+agentNum-
		# Also multi-agent with double target uses this gameConfig.
		config.agentTypes = ["srdqn", "srdqn","srdqn","srdqn"]
		config.to_prev_ai = [3,-1,-1,-1]
	elif config.gameConfig == 2: # one agent is run by DNN- Also, load-model loads from brain-3+agentNum-
		# Also multi-agent with double target uses this gameConfig.
		config.agentTypes = ["srdqn", "srdqn","srdqn","srdqn"]
		config.to_prev_ai = [3,-1,-1,-1]
	elif config.gameConfig == 3: 
		config.agentTypes = ["srdqn", "bs","bs","bs"]
	elif config.gameConfig == 4: 
		config.agentTypes = ["bs", "srdqn","bs","bs"]
	elif config.gameConfig == 5: 
		config.agentTypes = ["bs", "bs","srdqn","bs"]
	elif config.gameConfig == 6: 
		config.agentTypes = ["bs", "bs","bs","srdqn"]
	elif config.gameConfig == 7: 
		config.agentTypes = ["srdqn", "Strm","Strm","Strm"]
	elif config.gameConfig == 8: 
		config.agentTypes = ["Strm", "srdqn","Strm","Strm"]
	elif config.gameConfig == 9: 
		config.agentTypes = ["Strm", "Strm","srdqn","Strm"]
	elif config.gameConfig == 10: 
		config.agentTypes = ["Strm", "Strm","Strm","srdqn"]
	elif config.gameConfig == 11: 
		config.agentTypes = ["srdqn", "rnd","rnd","rnd"]
	elif config.gameConfig == 12: 
		config.agentTypes = ["rnd", "srdqn","rnd","rnd"]
	elif config.gameConfig == 13: 
		config.agentTypes = ["rnd", "rnd","srdqn","rnd"]
	elif config.gameConfig == 14: 
		config.agentTypes = ["rnd", "rnd","rnd","srdqn"]
	elif config.gameConfig == 15: 
		config.agentTypes = ["Strm", "bs","bs","bs"]		
	elif config.gameConfig == 16: 
		config.agentTypes = ["bs", "Strm","bs","bs"]		
	elif config.gameConfig == 17: 
		config.agentTypes = ["bs", "bs","Strm","bs"]		
	elif config.gameConfig == 18: 
		config.agentTypes = ["bs", "bs","bs","Strm"]
	elif config.gameConfig == 19: 
		config.agentTypes = ["rnd", "bs","bs","bs"]		
	elif config.gameConfig == 20: 
		config.agentTypes = ["bs", "rnd","bs","bs"]		
	elif config.gameConfig == 21: 
		config.agentTypes = ["bs", "bs","rnd","bs"]		
	elif config.gameConfig == 22: 
		config.agentTypes = ["bs", "bs","bs","rnd"]						
	elif config.gameConfig == 23: 
		config.agentTypes = ["Strm", "Strm","Strm","Strm"]
	elif config.gameConfig == 24: 
		config.agentTypes = ["rnd", "rnd","rnd","rnd"]		
	elif config.gameConfig == 25: 
		config.agentTypes = ["bs", "bs","bs","bs"]
	elif config.gameConfig == 26: 
		config.agentTypes = ["bs", "Strm","Strm","Strm"]
	elif config.gameConfig == 27: 
		config.agentTypes = ["Strm", "bs","Strm","Strm"]
	elif config.gameConfig == 28: 
		config.agentTypes = ["Strm", "Strm","bs","Strm"]
	elif config.gameConfig == 29: 
		config.agentTypes = ["Strm", "Strm","Strm","bs"]
	elif config.gameConfig == 30: 
		config.agentTypes = ["bs", "rnd","rnd","rnd"]
	elif config.gameConfig == 31: 
		config.agentTypes = ["rnd", "bs","rnd","rnd"]
	elif config.gameConfig == 32: 
		config.agentTypes = ["rnd", "rnd","bs","rnd"]
	elif config.gameConfig == 33: 
		config.agentTypes = ["rnd", "rnd","rnd","bs"]		
	else:
		config.agentTypes = ["bs", "bs","bs","bs"]

def fillnodes(config):
	if config.NoHiLayer == 2:
		config.nodes = [config.stateDim * config.multPerdInpt, config.node1,config.node2,config.actionListLen]
	elif config.NoHiLayer == 3:
		config.nodes = [config.stateDim * config.multPerdInpt, config.node1,config.node2,config.node3,config.actionListLen]


def setSavedDimentionPerBrain(config):
	if config.ifUsePreviousModel and not config.iftl:
		if config.demandDistribution == 0 and config.demandUp == 9 and config.demandLow == 0 and config.actionUp == 8:
			if config.gameConfig == 3:
				config.multPerdInpt = 5
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61
			elif config.gameConfig == 4:
				config.multPerdInpt = 10
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61
			elif config.gameConfig == 5:
				config.multPerdInpt = 5
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 6:
				config.multPerdInpt = 5
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 7:
				config.multPerdInpt = 10
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 8:
				config.multPerdInpt = 10
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 9:
				config.multPerdInpt = 10
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 10:
				config.multPerdInpt = 10
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 11:
				config.multPerdInpt = 5
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 12:
				config.multPerdInpt = 5
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 13:
				config.multPerdInpt = 10
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 14:
				config.multPerdInpt = 5
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
		
		elif config.demandDistribution == 1 and config.demandMu == 10 and config.demandSigma == 2 and config.actionUp == 5:
			if config.gameConfig == 3:
				config.multPerdInpt = 5
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61
			elif config.gameConfig == 4:
				config.multPerdInpt = 5
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61
			elif config.gameConfig == 5:
				config.multPerdInpt = 5
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 6:
				config.multPerdInpt = 10
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 7:
				config.multPerdInpt = 10
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 8:
				config.multPerdInpt = 10
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 9:
				config.multPerdInpt = 10
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 10:
				config.multPerdInpt = 10
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 11:
				config.multPerdInpt = 10
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 12:
				config.multPerdInpt = 10
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 13:
				config.multPerdInpt = 5
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 14:
				config.multPerdInpt = 10
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		

		elif config.demandDistribution == 2 and config.demandUp == 9 and config.demandLow == 0 and config.actionUp == 8:
			if config.gameConfig == 3:
				config.multPerdInpt = 10
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61
			elif config.gameConfig == 4:
				config.multPerdInpt = 10
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61
			elif config.gameConfig == 5:
				config.multPerdInpt = 10
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 6:
				config.multPerdInpt = 5
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 7:
				config.multPerdInpt = 5
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 8:
				config.multPerdInpt = 10
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 9:
				config.multPerdInpt = 5
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 10:
				config.multPerdInpt = 10
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 11:
				config.multPerdInpt = 10
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 12:
				config.multPerdInpt = 5
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 13:
				config.multPerdInpt = 5
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		
			elif config.gameConfig == 14:
				config.multPerdInpt = 10
				config.NoHiLayer = 3
				config.node1=180
				config.node2=130
				config.node3=61		

		elif config.demandDistribution != 3 and config.demandDistribution != 4:
			if config.gameConfig == 7:
				config.dnnUpCnt = 10000
				config.multPerdInpt = 5
				config.NoHiLayer = 2
				config.lr0 = 0.001
			elif config.gameConfig == 8:
				config.dnnUpCnt = 5000
				config.multPerdInpt = 5
				config.NoHiLayer = 2 # this should be 3
				config.lr0 = 0.00025
			elif config.gameConfig == 9:
				config.dnnUpCnt = 5000
				config.multPerdInpt = 3
				config.NoHiLayer = 2
				config.lr0 = 0.001
			elif config.gameConfig == 10:
				config.dnnUpCnt = 5000
				config.multPerdInpt = 3 # it should be 5 
				config.NoHiLayer = 2
				config.lr0 = 0.001

def set_optimal(config):
	if config.demandDistribution == 0:
		if config.cp1==2 and config.ch1==2 and config.ch2==2 and config.ch3==2 and config.ch4==2 :
			config.f1 = 8.
			config.f2 = 8.
			config.f3 = 0.
			config.f4 = 0.

def get_config():
	# config, unparsed = parser.parse_known_args()
	config = update_config(config)

	return config, unparsed

def fill_leadtime_initial_values(config):
	config.leadRecItemLow = [config.leadRecItem1, config.leadRecItem2, config.leadRecItem3, config.leadRecItem4]
	config.leadRecItemUp = [config.leadRecItem1, config.leadRecItem2, config.leadRecItem3, config.leadRecItem4]
	config.leadRecOrderLow = [config.leadRecOrder1, config.leadRecOrder2, config.leadRecOrder3, config.leadRecOrder4]
	config.leadRecOrderUp = [config.leadRecOrder1, config.leadRecOrder2, config.leadRecOrder3, config.leadRecOrder4]
	config.ILInit = [config.ILInit1, config.ILInit2, config.ILInit3, config.ILInit4]
	config.AOInit = [config.AOInit1, config.AOInit2, config.AOInit3, config.AOInit4]
	config.ASInit = [config.ASInit1, config.ASInit2, config.ASInit3, config.ASInit4]

def get_auxuliary_leadtime_initial_values(config):
	config.leadRecOrderUp_aux = [config.leadRecOrder1, config.leadRecOrder2, config.leadRecOrder3, config.leadRecOrder4]
	config.leadRecItemUp_aux = [config.leadRecItem1, config.leadRecItem2, config.leadRecItem3, config.leadRecItem4]

def fix_lead_time_manufacturer(config):
	if config.leadRecOrder4 > 0:
		config.leadRecItem4 += config.leadRecOrder4
		config.leadRecOrder4 = 0 

def set_sterman_parameters(config):
	config.alpha_b =[config.alpha_b1, config.alpha_b2, config.alpha_b3, config.alpha_b4]
	config.betta_b =[config.betta_b1, config.betta_b2, config.betta_b3, config.betta_b4]	


def update_config(config):
	config.actionList = buildActionList(config)		# The list of the available actions
	config.actionListLen = len(config.actionList)		# the length of the action list
		
	# set_optimal(config)
	config.f = [config.f1, config.f2, config.f3, config.f4] # [6.4, 2.88, 2.08, 0.8]

	config.actionListLen=len(config.actionList)
	if config.demandDistribution == 0:
		config.actionListOpt=list(range(0, int(max(config.actionUp*30+1, 3*sum(config.f))), 1))
	else:
		config.actionListOpt=list(range(0, int(max(config.actionUp*30+1, 7*sum(config.f))), 1))
	config.actionListLenOpt=len(config.actionListOpt)
	config.agentTypes=['dnn', 'dnn', 'dnn', 'dnn']
	config.saveFigInt = [config.saveFigIntLow, config.saveFigIntUp]
	
	if config.gameConfig == 0:
		config.NoAgent=min(config.NoAgent,len(config.agentTypes))
		config.agentTypes=[config.agent_type1,config.agent_type2,config.agent_type3,config.agent_type4]
	else:
		config.NoAgent=4
		setAgentType(config)					# set the agent brain types according to ifFourDNNtrain, ...

	config.c_h =[config.ch1, config.ch2, config.ch3, config.ch4]
	config.c_p =[config.cp1, config.cp2, config.cp3, config.cp4]

	config.stateDim= getStateDim(config) # Number of elements in the state description - Depends on ifUseASAO		
	np.random.seed(seed = config.seed)
	setSavedDimentionPerBrain(config) # set the parameters of pre_trained model. 
	fillnodes(config)			# create the structure of network nodes 	
	get_auxuliary_leadtime_initial_values(config)
	fix_lead_time_manufacturer(config)
	fill_leadtime_initial_values(config)
	set_sterman_parameters(config)

	return config

