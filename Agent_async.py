from operator import and_
from speedyibl import Agent
from collections import deque
import itertools
from warnings import warn
import copy
import sys
import asyncio
import socketio
import time
import random


class AgentIBL(Agent):

	# """ Agent """
	def __init__(self, outputs, bot_name, default_utility = None, Hash = True, delay_feedback = True):
		super(AgentIBL, self).__init__(default_utility=default_utility)
		# '''
		# :param dict config: Dictionary containing hyperparameters
		# '''
		self.state = 'disconnected'
		self.outputs = outputs
		self.options = {}
		self.episode_history = []
		self.hash = Hash
		self.delay_feedback = delay_feedback
		self.mismatchPenalty = 1
		self.last_action = 1
		self.option = 1
		self.bot_name = bot_name
		self.debug = 2
		self.similarity_max = [0, 300, 1, 1, 1, 1, 1, 1, 1, 1]

		self.similarity([0], lambda x, y: 1)
		
		for i in range(1, len(self.similarity_max)):
			self.similarity([i], boundedLinearSimilarity(0, self.similarity_max[i]))
		
		
		self.sio = socketio.AsyncClient()
		self.end_loop = asyncio.Event()
		self.end_game = asyncio.Event()
		self.free = asyncio.Event()
		self.in_game = asyncio.Event()
		self.state_map = []
		self.players = {}
		self.scoreboard = {}
		self.remaining_time = 0
		self.action_queue = deque()
		self.key_code_dict = {"up": 38, "left": 37, "right": 39, "down": 40, "enter": 13, "stay": 0}
		self.move_dict = {(-1, 0): "up", (0, 1): "right", (1, 0): "down", (0, -1): "left", (0, 0): "stay"}
		self.enter_pressed = False
		self.enter_pressed_time = 0
		self.episode_num = 0
		
		
	def debugRecv(self, event, data):
		if self.debug >= 2:
			print('<<<', event, data)
	
	def debugSend(self, event, data):
		if self.debug >= 2:
			print('>>>', event, data)
	
	def announce(self, msg, *args):
		if self.debug >= 1:
			print('---', msg, *args)
		
	async def connectServer(self, url):
		self.free.clear()
		await self.sio.connect(url, socketio_path='/ws/socket.io')
	
	async def onConnect(self):
		self.debugRecv('connected', None)
		self.announce('connected')
		await self.sio.emit('join_room', {'uid': self.bot_name, 'agent_type': "bot"})
		await asyncio.sleep(1)
		await self.sio.emit('ready', {'uid': self.bot_name})
		
	
	# Starting a new episode
	async def onStart(self, data):
		self.state = 'in_game'
		#self.loop_event.set()
		self.in_game.set()
		self.free.set()
		self.episode_num += 1
		self.prior_counts = {'dire':0, 'safe':0, 'obstacle':0} #dire, safe, obstacle visible counts
		self.prior_rescued = 0 #count of victims rescued
		self.prior_revealed = 0
		self.prior_player_positions = {}
		self.leader = ''
		self.prior_leader_position = [0, 0]
		self.decisions = []
		#self.rewards = []

	
	async def onWaiting(self, *args):
		if self.state != 'lobby':
			self.state = 'lobby'
			self.in_game.clear()
			self.free.clear()
			await self.sio.emit('ready', {'uid': self.bot_name})

	async def onEndGame(self, *args):
		self.state = 'finished'
		self.in_game.clear()
		self.end_game.set()
		self.debugRecv('disconnected', None)
		self.announce('disconnected')
		await self.sio.disconnect()
		return
	
	
	async def triggerDecision(self, trackers, visible_counts):

		print("making decision")
		
		# Compute representation values
		map_area = (len(self.state_map) * len(self.state_map[0]))
		percent_unexplored = trackers['tiles_revealed'] / map_area
		dire_victims_visible = visible_counts['dire']
		dire_victims_rescued = self.scoreboard['red'] + self.scoreboard['yellow']
		safe_victims_visible = visible_counts['safe']
		safe_victims_rescued = self.scoreboard['green']
		obstacles_visible = visible_counts['obstacle']
		common_attributes = [self.episode_num, self.remaining_time, percent_unexplored, 
					dire_victims_visible, dire_victims_rescued, 
					safe_victims_visible, safe_victims_rescued, 
					obstacles_visible]
		
		# Create list of available actions
		available_actions = [action for action, count in visible_counts.items() if count > 0]

		# Compute shortest paths between agents and nearest victim / obstacle
		agents = [uid for uid in self.players]
		queues_dict = self.processPaths(agents, available_actions)
		flattened_queues_dict = {(uid, action): action_info for uid, uid_info in queues_dict.items() for action, action_info in uid_info['actions'].items()} 
		options_info = sortDictWithCustomOrder(flattened_queues_dict, self.bot_name)

		# For follow actions, if the other agent is already within 2 units of self, remove from choice list
		# Create list of available choices
		choices = []
		for option, info in options_info.items():
			if option[0] != self.bot_name and option[1] != "follow":
				goal_coord = info['path'][-1]
				final_path = self.bfs(goal_coord)
				self_path_length = len(final_path)
				if self_path_length > 0:
					other_path_length = len(info['path'])
					info['path'] = final_path # replace the other-to-object path with self-to-object
					choices.append((tuple(common_attributes + [self_path_length, other_path_length]), option))
			elif option[0] != self.bot_name and option[1] == "follow":
				if len(info['path']) > 1:
					path_length = len(info['path'])
					choices.append((tuple(common_attributes + [path_length, path_length]), option))

			else:
				path_length = len(info['path'])
				if path_length > 0:
					choices.append((tuple(common_attributes + [path_length, path_length]), option))
		
		# Make a decision from available choices

		for i in range(1, len(self.similarity_max)):
			for choice in choices:
				if choice[0][i] > self.similarity_max[i]:
					self.similarity_max[i] = choice[0][i]
					self.similarity([i], boundedLinearSimilarity(0, self.similarity_max[i]))
		
		if self.in_game.is_set() == False:
				return
		decision = self.choose(choices)
		print(decision)
		#print(self.instances())
		
		# Initialize decision's reward as 0 and append decision to history for future updating
		self.respond(0)
		self.decisions.append((decision[0], decision[1]))
		#self.rewards.append(0)

		# Execute the decision
		await self.executeDecision(decision, options_info[decision[1]])


	async def executeDecision(self, decision, info):

		#self.free.clear()

		who = decision[1][0]
		what = decision[1][1]

		# Path planning		
		#path = info['path']
		goal_tile = info['path'][-1]
		#self_coord = self.players[self.bot_name]['coord']
		#if who != self.bot_name and what != "explore":
		#	path = self.bfs(goal_tile)
		
		# Planning and executing initial path
		reached_goal = False
		while reached_goal == False:

			if self.in_game.is_set() == False:
				return
			
			self_coord = self.players[self.bot_name]['coord']
			
			path = self.bfs(goal_tile)
			#print(f"current: {self_coord}, path: {path}")
			# Make keypresses
			keypresses = deque()
			old_coord = self_coord
			for i in range(len(path)):
				coord = path[i]
				direction = self.move_dict[(coord[0] - old_coord[0], coord[1] - old_coord[1])]
				keypresses.append([direction, "press"])
				old_coord = coord

			await self.executeKeypresses(keypresses)

			if self.end_game.is_set():
				return
			
			data = await self.sio.call('request_update', {'uid': self.bot_name})
			self.state_map = data['map'] 
			self.remaining_time = data['remaining_time']
			self.players = data['players']
			for uid, uid_info in self.players.items():
				uid_info['coord'] = tuple(uid_info['coord'])
			

			if abs(self.players[self.bot_name]['coord'][0] - goal_tile[0]) + abs(self.players[self.bot_name]['coord'][1] - goal_tile[1]) < 2:
				reached_goal = True
			
		# Assuming that we reached the goal, now to monitor if decision is complete
		# If decision to explore, use timer and available squares?
		# If decision to follow, use timer?
		# If decision to clear rubble, check if rubble is cleared, time left, and if there is progress on clearing
		# If decision to rescue, check if victim is rescued, time left, and if there is progress on rescuing

		prev_progress = 0
		action_start_time = time.time()
		goal_y = goal_tile[0]
		goal_x = goal_tile[1]

		while True:

			if self.in_game.is_set() == False:
				return

			data = await self.sio.call('request_update', {'uid': self.bot_name})
			self.state_map = data['map'] 
			goal_state = self.state_map[goal_y][goal_x]
			self.remaining_time = data['remaining_time']
			self.players = data['players']

			for uid, uid_info in self.players.items():
				uid_info['coord'] = tuple(uid_info['coord'])
			cur_time = time.time()

			# Decision to follow
			if what == "follow":
				if cur_time - action_start_time >= 5:
					break
				else:
					leader_position = self.players[who]['coord']
					self_position = self.players[self.bot_name]['coord']
					
					keypresses = deque()
					if manhattanDistance(self_position, leader_position) > 2:
						update_path = self.bfs(leader_position)
						old_coord = self.players[self.bot_name]['coord']

						for i in range(1, len(update_path)-1):
							coord = update_path[i]
							direction = self.move_dict[(coord[0] - old_coord[0], coord[1] - old_coord[1])]
							keypresses.append([direction, "press"])
							old_coord = coord
					else:
						keypresses.append(["stay", "press"])

			elif what == "explore":
				queue_dict = self.processPaths([self.bot_name], ["explore"])
				update_path = queue_dict[self.bot_name]['actions']['explore']['path']
				
				if len(update_path) == 0 or cur_time - action_start_time >= 8:
					break
				else:
					old_coord = self.players[self.bot_name]['coord']
					keypresses = deque()
					
					for i in range(1, len(update_path)):
						coord = update_path[i]
						direction = self.move_dict[(coord[0] - old_coord[0], coord[1] - old_coord[1])]
						keypresses.append([direction, "press"])
						old_coord = coord
			
			elif what == "obstacle" and self.players[self.bot_name]['role'] == "engineer":
				if (goal_state['progress'] - prev_progress == 0 and cur_time - action_start_time >= 5) or goal_state['feature'] not in ["door", "rubble"]:
					break
				else:
					if goal_state['engaged'] == False:
						prev_progress = goal_state['progress']
						keypresses.append(["enter", "press"])
					else:
						keypresses.append(["enter", "hold"])
			elif (what == "dire" or what == "safe") and self.players[self.bot_name]['role'] == "engineer":
				if (goal_state['progress'] - prev_progress == 0 and cur_time - action_start_time >= 5) or goal_state['feature'] not in ["red", "yellow", "green"]:
					break
				
				else:
					keypresses.append(["stay", "press"])
			
			elif (what == "dire" or what == "safe") and self.players[self.bot_name]['role'] == "medic":
				if goal_state['feature'] not in ["red", "yellow", "green"]:
					break
				else:
					if goal_state['engaged'] == False:
						prev_progress = goal_state['progress']
						keypresses.append(["enter", "press"])
					else:
						keypresses.append(["enter", "hold"])
			
			await self.executeKeypresses(keypresses)
		
		self.free.set()
			

	def processTrackers(self):
		trackers = {'red': 0, 'yellow': 0, 'green': 0, 'rubble': 0, 'door': 0, 'tiles_revealed': 0}
		for i in range(len(self.state_map)):
			for j in range(len(self.state_map[i])):
				if self.state_map[i][j]['revealed'] == 1: 
					trackers['tiles_revealed'] += 1
					tile_feature = self.state_map[i][j]['feature']
					if tile_feature in trackers:
						trackers[tile_feature] += 1

		return trackers
	
	def processPaths(self, agents, available_actions):
		# Breadth first search while keeping track of counters and paths for each relevant instance attribute
		self_y, self_x = self.players[self.bot_name]['coord']
		queues_dict = {}

		for uid in agents:
			y, x = self.players[uid]['coord']

			if uid == self.bot_name:

				queues_dict[uid] = {'queue': deque([((y, x), "root")]), 
						'visited': {(y, x): "root"}, 
						'actions': {key: {'path': [], 'reached': False}.copy() for key in (["explore"] + available_actions)},
						'reached': False}
			
			else:
				queues_dict[uid] = {'queue': deque([((y, x), "root")]), 
						'visited': {(y, x): "root"}, 
						'actions': {key: {'path': [], 'reached': False}.copy() for key in (["follow"] + available_actions)},
						'reached': False}


		# queues: visible counters, self to dire, self to safe, self to obstacles, other to self, other to dire, other to safe, other to obstacles
		first_tile = True
		def allReached(temp_dict):
			for key, info in temp_dict.items():
				if info['reached'] == False:
						return False
			return True
		
		#nodes_expanded = 0

		while not allReached(queues_dict):
			for uid, uid_info in queues_dict.items():
				if uid_info['reached'] == False:
					path = uid_info['queue'].popleft()
					y, x = path[0]
					tile_feature = self.state_map[y][x]['feature']

					for action, action_info in uid_info['actions'].items():
						if action_info['reached'] == False:
							if (action == "dire" and tile_feature in ['red', 'yellow']) or \
									(action == "safe" and tile_feature in ['green'] ) or \
										(action == "obstacle" and tile_feature in ['rubble', 'door']) or \
											(action == "follow" and (y, x) == (self_y, self_x)):
								# Reconstruct path
								action_info['path'] = reconstructPath(uid_info['visited'], (y, x))
								action_info['reached'] = True
								#print(f"reached: {(uid, action, nodes_expanded)}")
							
							# Find nearest tile with unrevealed adjacent tiles
							elif uid==self.bot_name and action == "explore" and tile_feature == '':
								for y2, x2 in ((y, x+1), (y, x-1), (y+1, x), (y-1, x)):
									if self.state_map[y2][x2]['revealed'] == 0:
										action_info['path'] = reconstructPath(uid_info['visited'], (y, x))
										action_info['reached'] = True
										#print(f"reached: {(uid, action, nodes_expanded)}")
										break

					if allReached(uid_info['actions']):
						uid_info['reached'] = True
						
					if uid_info['reached'] == False and (tile_feature == "" or first_tile == True):
						for y2, x2 in ((y, x+1), (y, x-1), (y+1, x), (y-1, x)):
							if self.state_map[y2][x2]['revealed'] == 1 and self.state_map[y2][x2]['feature'] != "wall" and (y2, x2) not in uid_info['visited']:
								uid_info['queue'].append([(y2, x2), (y, x)])
								uid_info['visited'][(y2, x2)] = (y, x)

					if bool(uid_info['queue']) == False:
						uid_info['reached'] = True
						for action, action_info in uid_info['actions'].items():
							if action_info['reached'] == False:
								action_info['reached'] = True
								#print(f"reached: {(uid, action, nodes_expanded)}")
								if action == "explore":
									action_info['path'] = []
								else:
									action_info['path'] = reconstructPath(uid_info['visited'], (y, x))
									
			first_tile = False
			#nodes_expanded += 1

		return queues_dict
	


	def bfs(self, goal_tile):

		# Bi-directional
		# Store visited tiles as tile: parent entries in a dictionary

		queue = deque([(self.players[self.bot_name]['coord'], "root", 1), (goal_tile, "root", -1)]) # 1 forward, -1 backwards
		visited = {1: {self.players[self.bot_name]['coord']: "root"}, -1: {goal_tile: "root"}}

		while queue:
			cur_tile = queue.popleft()
			cur_y, cur_x = cur_tile[0] # Obtain coordinates of tile

			cur_parent = cur_tile[1]
			cur_direction = cur_tile[2]
			#tile_feature = self.state_map[cur_y][cur_x]['feature']
			visited[cur_direction][(cur_y, cur_x)] = cur_parent

			if (cur_y, cur_x) in visited[-1 * cur_direction]:
				
				# Reconstruct path

				start_path = reconstructPath(visited[1], (cur_y, cur_x))
				end_path = reconstructPath(visited[-1], (cur_y, cur_x), reverse = True)
				end_path.popleft()
				
				return(list(start_path + end_path))
			
			#elif tile_feature == "" or cur_parent == "root":
			for y2, x2 in ((cur_y, cur_x+1), (cur_y, cur_x-1), (cur_y+1, cur_x), (cur_y-1, cur_x)):
				if self.state_map[y2][x2]['revealed'] == 1 and self.state_map[y2][x2]['feature'] == "" and (y2, x2) not in visited[cur_direction]:
					queue.append([(y2, x2), (cur_y, cur_x), cur_direction])
					visited[cur_direction][(y2, x2)] = (cur_y, cur_x)
		
			if bool(queue) == False:
				return [self.players[self.bot_name]['coord']]

	async def gameLoop(self):
		
		while True:

			if self.end_game.is_set() == True:
				break

			# Only run if I'm free
			await self.free.wait()
			self.free.clear()

			# Request updates from server and update my internal states accordingly
			data = await self.sio.call('request_update', {'uid': self.bot_name})
			self.state_map = data['map'] 
			self.remaining_time = data['remaining_time']
			self.players = data['players']

			# Necessary to convert from list to tuple
			for uid, uid_info in self.players.items():
				uid_info['coord'] = tuple(uid_info['coord'])
			
			self.scoreboard = data['scoreboard']

			trackers = self.processTrackers()
			visible_counts = {'dire': trackers['red'] + trackers['yellow'], 
						'safe': trackers['green'], 
						'obstacle': trackers['rubble'] + trackers['door']}
		
			# Update the rewards of my instances if necessary
			total_rescued = 0
			for key, value in self.scoreboard.items():
				total_rescued += value
			rescued_increment = total_rescued - self.prior_rescued
			if rescued_increment > 0:
				self.increment_feedback(rescued_increment, self.decisions)
				self.prior_rescued = total_rescued

			await self.triggerDecision(trackers, visible_counts)

	async def executeKeypresses(self, keypresses):
		while keypresses:
			await self.sio.sleep(random.uniform(0.05, 0.3))
			key, action = keypresses.popleft()
			if self.end_game.is_set():
				break
			await self.sio.call('keyEvent', {'uid': self.bot_name, 'event': action, 'key': self.key_code_dict[key]})
			#if key != "enter": # Immediately release direction keys upon pressing
				#await self.sio.call('keyEvent', {'uid': self.bot_name, 'event': 'release', 'key': self.key_code_dict[key]})
				# This would be where we would insert the model running (or at least the actions)
				#await self.sio.mit('keyEvent', {'uid': self.bot_name, 'event': "press", 'key': next_key_dict[last_key]})
				#await self.sio.emit('keyEvent', {'uid': self.bot_name, 'event': "release", 'key': next_key_dict[last_key]})
				#last_key = next_key_dict[last_key]

			# Should maintain decision but change course if met with an obstacle
			# Should interrupt decision if the goal is no longer present (i.e. when rescuing a victim)
			# Should recalculate if medic has moved...

			#data = await self.sio.call('request_update', {'uid': self.bot_name})
			#self.state_map = data['map'] 
			#self.remaining_time = data['remaining_time']
			#self.players = data['players']

		if bool(keypresses) == False:
			self.free.set()
		#return

async def main():
	
	agent = AgentIBL(outputs = ["right"], bot_name = f'bot_{time.time()}')
	# Define all listeners here
	agent.sio.on('connect', agent.onConnect)
	agent.sio.on('start_game', agent.onStart)
	agent.sio.on('waiting', agent.onWaiting)
	agent.sio.on('end_episode', agent.onWaiting)
	agent.sio.on('end_game', agent.onEndGame)
	#agent.sio.on('refresh', agent.onRefresh)
	
	# Start loop
	#agent_explore_loop = asyncio.create_task(agent.exploreLoop())

	await agent.connectServer('http://localhost:5704')
	agent_game_loop = asyncio.create_task(agent.gameLoop())
	await agent_game_loop
	#await agent_explore_loop
	sys.exit()

def sortDictWithCustomOrder(input_dict, first_key):
	sorted_items = sorted(input_dict.items(), key=lambda item: (customSort(item[0], first_key), item))
	sorted_dict = dict(sorted_items)
	return sorted_dict


def customSort(key, first_key):
	player, action = key
	player_order = {first_key: 0}.get(player, 1)
	action_order = {"explore": 0, "follow": 1, "dire": 2, "safe": 3, "obstacle": 4}.get(action, 5)
	return player_order, action_order

def manhattanDistance(a, b):
	return(abs(a[0] - b[0]) + abs(a[1] - b[1]))

def posLinearSimilarity(x, y):
	if x <= 0 or y <= 0:
		raise ValueError(f"the arguments, {x} and {y}, are not both positive")
	if x == y:
		return 1
	if x > y:
		x, y = y, x
	return 1 - (y - x) / y

def boundedLinearSimilarity(minimum, maximum):

	if minimum >= maximum:
		raise ValueError(f"minimum, {minimum}, is not less than maximum, {maximum}")
	def _similarity(x, y):
		if x < minimum:
			warn(f"{x} is less than {minimum}, so {minimum} is instead being used in computing similarity")
			x = minimum
		elif x > maximum:
			warn(f"{x} is greater than {maximum}, so {maximum} is instead being used in computing similarity")
			x = maximum
		if y < minimum:
			warn(f"{y} is less than {minimum}, so {minimum} is instead being used in computing similarity")
			y = minimum
		elif y > maximum:
			warn(f"{y} is greater than {maximum}, so {maximum} is instead being used in computing similarity")
			y = maximum
		return 1 - abs(x - y) / abs(maximum - minimum)
	return _similarity

def reconstructPath(visited_dict, start_tile, reverse = False):
	path = deque([start_tile])
	parent = visited_dict[start_tile]
	while parent != "root":
		if reverse == False:
			path.appendleft(parent)
		else:
			path.append(parent)
		parent = visited_dict[parent]
	return path

if __name__ == '__main__':
	asyncio.run(main())