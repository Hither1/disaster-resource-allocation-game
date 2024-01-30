import numpy as np
class Agency:
  """
  Base class for decision-making agency.

  Args:
    strategy (str): 'bs': base stock or 'strm': Stermann
  """
  def __init__(self, world, pos, agentNum, config, mode='bot', strategy='bs'):
    self.world = world
    self.pos = np.array(pos)
    self.random = world.random
    self.base_stock = {'food': 2, 
                  'drink': 2, 
                  'staff': 1}
    self.strategy = strategy
    self.in_requests = []
    self.out_requests = []
    self.staff_team = []
    self.gamma = 0.95
    self._communication = 0
    self.mode = mode
    # physical motor noise amount
    self.u_noise = None
    # communication noise amount
    self.c_noise = None

    self.agentNum = agentNum
    self.config = config
    self.alpha_b = self.config.alpha_b[self.agentNum] # parameters for the formula
    self.betta_b = self.config.betta_b[self.agentNum] # parameters for the formula
    if self.config.demandDistribution == 0:
      self.a_b = np.mean((self.config.demandUp[self.agentNum], self.config.demandLow[self.agentNum])) # parameters for the formula
      self.b_b = np.mean((self.config.demandUp[self.agentNum], self.config.demandLow[self.agentNum])) * (np.mean((self.config.leadRecItemLow[self.agentNum], 
			self.config.leadRecItemUp[self.agentNum])) + np.mean((self.config.leadRecOrderLow[self.agentNum], self.config.leadRecOrderUp[self.agentNum]))) # parameters for the formula

    elif self.config.demandDistribution == 1 or self.config.demandDistribution == 3 or self.config.demandDistribution == 4:
      self.a_b = self.config.demandMu # parameters for the formula
      self.b_b = self.config.demandMu*(np.mean((self.config.leadRecItemLow[self.agentNum], 
			  self.config.leadRecItemUp[self.agentNum])) + np.mean((self.config.leadRecOrderLow[self.agentNum], self.config.leadRecOrderUp[self.agentNum]))) # parameters for the formula
    elif self.config.demandDistribution == 2:
      self.a_b = 8 # parameters for the formula
      self.b_b = (3/4.)*8*(np.mean((self.config.leadRecItemLow[self.agentNum] , 
			  self.config.leadRecItemUp[self.agentNum])) + np.mean((self.config.leadRecOrderLow[self.agentNum] , self.config.leadRecOrderUp[self.agentNum]))) # parameters for the formula
    elif self.config.demandDistribution == 3:
      self.a_b = 10 # parameters for the formula
      self.b_b = 7 * (np.mean((self.config.leadRecItemLow[self.agentNum], 
			  self.config.leadRecItemUp[self.agentNum])) + np.mean((self.config.leadRecOrderLow[self.agentNum] , self.config.leadRecOrderUp[self.agentNum]))) # parameters for the formula

  @property
  def texture(self):
    raise 'unknown'
  
  # updates the IL and OO at time t, after recieving "rec" number of items 
  def receiveItems(self):
    for resource in self.base_stock.keys():
      self.inventory[resource] = int(self.inventory[resource] + self.AS[resource][self.curTime]) # inverntory level update
      if resource == 'staff':
        for _ in range(int(self.AS[resource][self.curTime])):
          self.staff_team.append(Person('staff', 5))
      self.OO[resource] = max(0, int(self.OO[resource] - self.AS[resource][self.curTime])) # invertory in transient update
    
  def _process_requests(self):
    requests = []
    for request in self.in_requests:
      destination, request = request[0], request[1]
      inventory = self.inventory.keys()
      resources = [word for word in inventory if word.lower() in request]
      quantities = re.findall(r'\d+', request)

      for quantity, resource in zip(quantities, resources):
        if int(quantity) > 0:
          requests.append([destination, quantity, resource])

    return requests
  
  def _make_orders(self, goal):
    # print(self, goal)
    self._communication = 0
    order = {}
    if self.strategy == 'bs':
      for resource in self.base_stock.keys():
        if self.config.demandDistribution == 2:
          if self.curTime and self.config.use_initial_BS <= 4:
            # self.action[np.argmin(np.abs(np.array(self.config.actionListOpt)-\
						# 		max(0, (self.int_bslBaseStock - (self.inventory[resource] + self.OO - self.AO[resource][self.curTime]))) ))]
            self.action = np.argmin(np.abs(np.array(self.config.actionListOpt)-\
								max(0, (self.int_bslBaseStock - (self.inventory[resource] + self.OO[resource] - self.AO[resource][self.curTime]))) )) 	
          else: 
            # self.action[np.argmin(np.abs(np.array(self.config.actionListOpt)-\
						# 		max(0, (self.base_stock[resource] - (self.inventory[resource] + self.OO - self.AO[self.curTime]))) ))] 
            self.action = np.argmin(np.abs(np.array(self.config.actionListOpt)-\
								max(0, (self.base_stock[resource] - (self.inventory[resource] + self.OO[resource] - self.AO[resource][self.curTime]))) ))
        else:
          # self.action[np.argmin(np.abs(np.array(self.config.actionListOpt)-\
					# 			max(0, (self.base_stock[resource] - (self.inventory[resource] + self.OO - self.AO[self.curTime]))) ))] 
          # self.action = np.argmin(np.abs(np.array(self.config.actionListOpt)-\
					# 		max(0, (self.base_stock[resource] - (self.inventory[resource] + self.OO[resource] - self.AO[resource][self.curTime]))) ))
          self.action = np.argmin(np.abs(np.array(self.config.actionListOpt)-\
							max(0, (goal[resource] - (self.inventory[resource] + self.OO[resource] - self.AO[resource][self.curTime]))) ))
          
        if self.action > 0: order[resource] = self.action

    elif self.strategy == 'strm':
      for resource in self.base_stock.keys():
        self.action = np.argmin(np.abs(np.array(self.config.actionListOpt)\
									-max(0, round(self.AO[resource][self.curTime] +\
									self.alpha_b * (self.inventory[resource] - self.a_b) +\
									self.betta_b * (self.OO[resource] - self.b_b)))))
        if self.action > 0: order[resource] = self.action
    
    elif self.strategy == 'gpt-4':
      pass

    if 'staff' in order.keys(): # TODO: Change this
      if self.name != 'Station':
        self.out_requests.append(f"{self.name}->Station: Please send {order['staff']} staff")
        self.OO['staff'] += order['staff']
        self._communication += 1
      del order['staff']

    request = f'{self.name}->Warehouse: Please send '
    for resource, quantity in order.items():
      if resource != 'staff':
        self.OO[resource] += quantity
        request += str(quantity) + ' ' + resource + ' '

    if order.keys():
      self.out_requests.append(request)
      self._communication += 1
    
    self.cumReward = self.gamma * self.cumReward + self.curReward
    self.curTime += 1

  def resetPlayer(self, T):
    self.OO = {key: 0 for key in self.base_stock.keys()}
    self.AS = {key: np.squeeze(np.zeros((1, T + max(self.config.leadRecItemUp) + max(self.config.leadRecOrderUp) + 10))) for key in self.base_stock.keys()}
    self.AO = {key: np.squeeze(np.zeros((1, T + max(self.config.leadRecItemUp) + max(self.config.leadRecOrderUp) + 10))) for key in self.base_stock.keys()}

    self.curReward = 0 # the reward observed at the current step
    self.cumReward = 0 # cumulative reward; reset at the begining of each episode	
    self.action= [] 
    self.hist = []
    self.hist2 = []
    self.srdqnBaseStock = []	# this holds the base stock levels that srdqn has came up with. added on Nov 8, 2017
    self.T = T
    self.nextObservation = []
    # if self.compTypeTrain == 'srdqn':
    #   self.brain.setInitState(self.curObservation) # sets the initial input of the network
    self.curTime = 0
    self.staff_team = []
    self.patients = []

  # This function returns a np.array of the current state of the agent	
  def getCurState(self, t=None):
    if t is None: t = self.curTime
    if self.config.ifUseASAO:
      if self.config.if_use_AS_t_plus_1:
        curState = np.array([[-1*(self.inventory[resource]<0)*self.inventory[resource], 
                              1*(self.inventory[resource]>0)*self.inventory[resource], 
                              self.OO[resource], 
                              self.AS[resource][t], 
                              self.AO[resource][t]] for resource in self.base_stock])
      else:
        # curState = np.array([[-1*(self.inventory[resource]<0)*self.inventory[resource], 
        #                       1*(self.inventory[resource]>0)*self.inventory[resource], 
        #                       self.OO[resource], 
        #                       self.AS[resource][t-1], 
        #                       self.AO[resource][t]] for resource in self.base_stock])
        curState = np.array([[self.inventory[resource], 
                              self.OO[resource], 
                              self.AS[resource][t-1], 
                              self.AO[resource][t]] for resource in self.base_stock])
    else:
      # curState = np.array([[-1*(self.inventory[resource]<0)*self.inventory[resource], 
      #                       1*(self.inventory[resource]>0)*self.inventory[resource], 
      #                       self.OO[resource]] for resource in self.base_stock])
      curState = np.array([[self.inventory[resource], 
                            self.OO[resource]] for resource in self.base_stock])

    if self.config.ifUseActionInD:
      a = self.config.actionList[np.argmax(self.action)]
      curState = np.concatenate((curState, np.array([a])))
    
    return curState.flatten()