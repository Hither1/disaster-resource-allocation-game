import numpy as np
import matplotlib.pyplot as plt

def demand(distribution='normal', mean=0, std_dev=1):
  if distribution == 'normal':
      number_initial_patients = np.random.normal(mean, std_dev, 1)
  elif distribution == 'poisson':
      lambda_parameter = 3.0
      number_initial_patients = np.random.poisson(lambda_parameter, 1)
  else:
      low = 10
      high = 14
      number_initial_patients = np.random.uniform(low, high, 1)

  return int(number_initial_patients)

def piecewise_function(x, noise='normal'):
    mean = np.piecewise(x, [(x >= 0) & (x <= 2), (x > 2) & (x <= 6), x > 6], [lambda x: -2*x + 6, lambda x: 2, lambda x: 0])
    noise = 0 # demand(noise)
    return mean + noise if x <= 6 else 0

def decaying_function(x, decay_rate=0.5, noise='normal'):
    mean = 6 * np.exp(-decay_rate * x)
    noise = demand(noise)
    return mean + noise

# x_values = np.linspace(0, 6, 400)
# y_piecewise = piecewise_function(x_values)
# y_decaying = decaying_function(x_values)

# plt.plot(x_values, y_piecewise, label='Ramp-type Demand', color='blue')
# plt.plot(x_values, y_decaying, label='Exponentially-varying Demand', color='red')

# plt.xlabel('Days (t)')
# plt.ylabel('#Injured People')
# plt.title('Time-varying Demand Functions')

# plt.legend()

# plt.grid(True)
# plt.show()
