import argparse

import numpy as np
try:
  import pygame
except ImportError:
  print('Please install the pygame package to use the GUI.')
  raise
from PIL import Image
import matplotlib.pyplot as plt
import crafter

def padding(data):
    max_length = max(len(sublist) for sublist in data)
    padded_data = [sublist + [np.nan] * (max_length - len(sublist)) for sublist in data]
    array_data = np.array(padded_data)

    return array_data

def main(config):
  keymap = {
      pygame.K_a: 'move_left',
      pygame.K_d: 'move_right',
      pygame.K_w: 'move_up',
      pygame.K_s: 'move_down',
      pygame.K_SPACE: 'do',
      pygame.K_TAB: 'sleep',

      pygame.K_r: 'place_stone',
      pygame.K_t: 'place_table',
      pygame.K_f: 'place_furnace',
      pygame.K_p: 'place_plant',

      pygame.K_1: 'make_wood_pickaxe',
      pygame.K_2: 'make_stone_pickaxe',
      pygame.K_3: 'make_iron_pickaxe',
      pygame.K_4: 'make_wood_sword',
      pygame.K_5: 'make_stone_sword',
      pygame.K_6: 'make_iron_sword',
  }
  print('Actions:')
  for key, action in keymap.items():
    print(f'  {pygame.key.name(key)}: {action}')

  crafter.constants.items['health']['max'] = config.health
  crafter.constants.items['health']['initial'] = config.health

  size = list(config.size)
  size[0] = config.window[0]
  size[1] = config.window[1]

  env = crafter.Env(config)
  env = crafter.Recorder(env, config.record)
  env.reset()

  achievements = set()
  duration = 0
  return_ = 0
  was_done = False
  print('Diamonds exist:', env.world.count('diamond'))

  pygame.init()
  screen = pygame.display.set_mode(config.window)
  clock = pygame.time.Clock()
  running = True

  rewards_record = []

  while running:

    # Rendering.
    image = env.render(size)
    if size != config.window:
      image = Image.fromarray(image)
      image = image.resize(config.window, resample=Image.NEAREST)
      image = np.array(image)
    surface = pygame.surfarray.make_surface(image.transpose((1, 0, 2)))
    screen.blit(surface, (0, 0))
    pygame.display.flip()
    clock.tick(config.fps)

    # Keyboard input.
    action = None
    pygame.event.pump()
    for event in pygame.event.get():
      if event.type == pygame.QUIT:
        running = False
      elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
        running = False
      elif event.type == pygame.KEYDOWN and event.key in keymap.keys():
        action = keymap[event.key]
    if action is None:
      pressed = pygame.key.get_pressed()
      for key, action in keymap.items():
        if pressed[key]:
          break
      else:
        if config.wait and not env._player.sleeping:
          continue
        else:
          action = 'noop'

    # Environment step.
    import time 
    time.sleep(1)
    _, rewards, done, _ = env.step(env.action_names.index(action))

    if len(env.shelter.patients) == 0:  # Press 'p' to toggle pause
      done = True
    duration += 1
    rewards_record.append(rewards[1:])

    # Achievements.
    unlocked = {
        name for name, count in env._player.achievements.items()
        if count > 0 and name not in achievements}
    for name in unlocked:
      achievements |= unlocked
      total = len(env._player.achievements.keys())
      print(f'Achievement ({len(achievements)}/{total}): {name}')
    if env._step > 0 and env._step % 100 == 0:
      print(f'Time step: {env._step}')
    if rewards[0]:
      print(f'Reward: {rewards[0]}')
      return_ += rewards[0]

    # Episode end.
    if done and not was_done:
      was_done = True
      print('Episode done!')
      print('Duration:', duration)
      print('Return:', return_)
      if config.death == 'quit':
        running = False
      if config.death == 'reset':
        print('\nStarting a new episode.')
        env.reset()
        achievements = set()
        was_done = False
        duration = 0
        return_ = 0
      if config.death == 'continue':
        pass

      pygame.quit()
      return rewards_record


if __name__ == '__main__':
  config, unparsed = crafter.config.get_config()
  repeat = 20
  rewards_records = []
  for _ in range(repeat):
    rewards_record = main(config)
    columns = list(map(list, zip(*rewards_record)))
    rewards_records.append(columns)

  env = crafter.Env(config)
  env.reset()
  
  for i, player in enumerate(env.players):
    column = padding([sublist[i] for sublist in rewards_records])
    mean = np.nanmean(column, axis=0)
    std = np.nanstd(column, axis=0)
    plt.plot(range(len(mean)), mean, label=player.name)
    plt.fill_between(range(len(mean)), mean - std, mean + std, alpha=0.5)

  plt.xlabel('Time step')
  plt.ylabel('Reward')
  plt.title(f'(Reward) Shelter: {env.shelter.strategy}, Warehouse: {env.warehouse.strategy}, Station: {env.station.strategy}')
  plt.legend()
  plt.show()
