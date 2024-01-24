import {constants} from './constants.js';

class Person {
    constructor(type, health = 5) {
      this.inventory = {};
      this.action = 'noop';
      this.sleeping = false;
      this.health = health;
      this._lastHealth = this.health;
  
    //   for (const [name, info] of Object.entries(constants.items)) {
    //     this.inventory[name] = info.initial;
    //   }
  
      if (type === 'injured') {
        this._admittedDays = 0;
      } 
    }
  
    get texture() {
      return this.sleeping ? 'player-sleep' : undefined;
    }
  }


class Agency {
    constructor(agentNum, config, strategy='bs', mode='computer') {
      this.base_stock = {'food': 2, 'drink': 2, 'staff': 1};
      this.removed = false;
      this.strategy = strategy;
      this.in_requests = [];
      this.out_requests = [];
      this.staff_team = [];
      this.gamma = 0.95;
      this.communication = 0;
      this.u_noise = null;
      this.c_noise = null;
      this.agentNum = agentNum;
      this.config = config;

      this.alpha_b = this.config.alpha_b[this.agentNum];
      this.betta_b = this.config.betta_b[this.agentNum];
      this.mode = mode;
      
      if (this.config.demandDistribution === 0) {
        this.a_b = (this.config.demandUp[this.agentNum] + this.config.demandLow[this.agentNum]) / 2;
        this.b_b = this.a_b * ((this.config.leadRecItemLow[this.agentNum] + this.config.leadRecItemUp[this.agentNum]) +
                              (this.config.leadRecOrderLow[this.agentNum] + this.config.leadRecOrderUp[this.agentNum]));
      } else if (this.config.demandDistribution === 1 || this.config.demandDistribution === 3 || this.config.demandDistribution === 4) {
        this.a_b = this.config.demandMu;
        this.b_b = this.config.demandMu * ((this.config.leadRecItemLow[this.agentNum] + this.config.leadRecItemUp[this.agentNum]) +
                                          (this.config.leadRecOrderLow[this.agentNum] + this.config.leadRecOrderUp[this.agentNum]));
      } else if (this.config.demandDistribution === 2) {
        this.a_b = 8;
        this.b_b = (3 / 4) * 8 * ((this.config.leadRecItemLow[this.agentNum] + this.config.leadRecItemUp[this.agentNum]) +
                                  (this.config.leadRecOrderLow[this.agentNum] + this.config.leadRecOrderUp[this.agentNum]));
      } else if (this.config.demandDistribution === 3) {
        this.a_b = 10;
        this.b_b = 7 * ((this.config.leadRecItemLow[this.agentNum] + this.config.leadRecItemUp[this.agentNum]) +
                        (this.config.leadRecOrderLow[this.agentNum] + this.config.leadRecOrderUp[this.agentNum]));
      }
    }
  
    get texture() {
      throw 'unknown';
    }
  
    receiveItems() {
      for (const resource in this.base_stock) {
        this.inventory[resource] = parseInt(this.inventory[resource] + this.AS[resource][this.curTime]);
        
        if (resource === 'staff') {
          for (let i = 0; i < parseInt(this.AS[resource][this.curTime]); i++) {
            this.staff_team.push(new Person('staff', 5));
          }
        }
        this.OO[resource] = Math.max(0, parseInt(this.OO[resource] - this.AS[resource][this.curTime]));
      }
    }
  
    _process_requests() {
            const requests = [];
            console.log('in process', this.in_requests)
            for (const request of this.in_requests) {
                const destination = request[0];
                const resource = request[1];
          
                const inventory = Object.keys(this.inventory);
                const resources = inventory.filter(word => word.toLowerCase().includes(resource));
          
                const quantities = resource.match(/\d+/g);
          
                for (let i = 0; i < quantities.length; i++) {
                  const quantity = quantities[i];
                  const requestedResource = resources[i];
                  if (parseInt(quantity) > 0) {
                    requests.push([destination, quantity, requestedResource]);
                  }
                }
            }
        

        return requests
    }

    _make_orders(userInputs) {
        if (this.mode === 'human') {
            if (userInputs[0]['food'] > 0) {
                this.out_requests.push(`${this.name}->Warehouse: Please send ${userInputs[0]['food']} food and ${userInputs[0]['drink']} drink`);
            }
            if (userInputs[0]['staff'] > 0) {
                this.out_requests.push(`${this.name}->Station: Please send ${userInputs[0]['staff']} staff`);
            }
        }
        else {
            this._communication = 0;
            const order = {};
      
            if (this.strategy === 'bs') {
                for (const resource in this.base_stock) {
                if (this.config.demandDistribution === 2) {
                    this.action = this.config.actionListOpt.findIndex((action) =>
                    Math.abs(action - Math.max(0, this.int_bslBaseStock - (this.inventory[resource] + this.OO[resource] - this.AO[resource][this.curTime])))
                );
                } else {
              this.action = this.config.actionListOpt.findIndex((action) =>
                Math.abs(action - Math.max(0, this.base_stock[resource] - (this.inventory[resource] + this.OO[resource] - this.AO[resource][this.curTime])))
              );
            }
      
            if (this.action > 0) {
              order[resource] = this.action;
            }
          }
        } else if (this.strategy === 'strm') {
          for (const resource in this.base_stock) {
            this.action = this.config.actionListOpt.findIndex((action) =>
              Math.abs(action - Math.max(0, Math.round(this.AO[resource][this.curTime] +
                this.alpha_b * (this.inventory[resource] - this.a_b) +
                this.betta_b * (this.OO[resource] - this.b_b))))
            );
      
            if (this.action > 0) {
              order[resource] = this.action;
            }
          }
        } else if (this.strategy === 'gpt-4') {
          // Handle gpt-4 strategy (if needed)
        }
      
        if ('staff' in order) {
          if (this.name !== 'Station') {
            this.out_requests.push(`${this.name}->Station: Please send ${order['staff']} staff`);
            this.OO['staff'] += order['staff'];
            this._communication += 1;
          }
          delete order['staff'];
        }
      
        let request = `${this.name}->Warehouse: Please send `;
        for (const [resource, quantity] of Object.entries(order)) {
          if (resource !== 'staff') {
            this.OO[resource] += quantity;
            request += `${quantity} ${resource} `;
          }
        }
      
        if (Object.keys(order).length > 0) {
          this.out_requests.push(request);
          this._communication += 1;
        }
      
        this.cumReward = this.gamma * this.cumReward + this.curReward;
        this.curTime += 1;
      }    }  

      resetPlayer(T) {
        this.OO = {};
        this.AS = {};
        this.AO = {};

        for (const key of Object.keys(this.base_stock)) {
            this.OO[key] = 0;
            this.AS[key] = Array.from({ length: T + Math.max(...this.config.leadRecItemUp) + Math.max(...this.config.leadRecOrderUp) + 10 }, () => 0);
            this.AO[key] = Array.from({ length: T + Math.max(...this.config.leadRecItemUp) + Math.max(...this.config.leadRecOrderUp) + 10 }, () => 0);
          }
      }
  
  }

export class Station extends Agency {
    constructor(agentNum, config) {
      super(agentNum, config);
      this.inventory = {
        'food': 9,
        'drink': 9,
        'staff': demand(12, 2),
      };
      this.staff_team = Array.from({ length: this.inventory['staff'] }, () => new Person('staff', 5));

      this._backorder = 0;
      this.strategy = 'bs';
    }
  
    get name() {
      return 'Station';
    }
  
    get reward() {
      return this.curReward;
    }
  
    resetPlayer(T) {
        super.resetPlayer(T);
  
        this.inventory = {
            'food': 9,
            'drink': 9,
            'staff': demand(12, 2),
        };
        this.staff_team = Array.from({ length: this.inventory['staff'] }, () => new Person('staff', 5));
    }
  
    step(_step, userInputs) {
      this._backorder = 0;


      this._make_decisions_on_requests(userInputs);

      this.receiveItems();
      this._update_inventory_stats();
      this.curReward = -this._backorder - this.communication;
  
      for (const [name, amount] of Object.entries(this.inventory)) {
        const maxmium = constants.items[name]['max'];
        this.inventory[name] = Math.min(amount, maxmium);
      }
    }
  
    _update_inventory_stats() {
      this.consumption = 0;
      const neededStaff = Math.max(this.inventory['staff'] - this.staff_team.length, 0);
  
      for (let i = 0; i < neededStaff; i++) {
        this.staff_team.push(new Person('staff', 0));
      }
  
      for (const staff of this.staff_team) {
        staff.health += Math.min(5, 1.5 + staff.health);
      }
    }
  
    _make_decisions_on_requests(userInputs) {
      // Part 1:
      if (this.mode === 'human') {
        userInputs[1]['staff'].forEach(([requester, quantity]) => {
                this.AO[resource][this.curTime] = quantity;
                requester.AS[resource][this.curTime + 1] += quantity;
                this.inventory[resource] -= quantity;
          });
      } else {
        this.in_requests = this._process_requests();
        this.in_requests.sort((a, b) => a[0].name.localeCompare(b[0].name));
  
        for (const request of this.in_requests) {
            const [requester, quantity, resource] = request;
            this.AO[resource][this.curTime] = quantity;
  
            const sending_quantity = Math.min(this.inventory[resource], quantity);
  
            for (let i = 0; i < sending_quantity; i++) {
                if (this.staff_team.length > 0 && this.staff_team[0].health > 4) {
                this.inventory[resource]--;
                requester.AS[resource][this.curTime + 1]++;
                this.staff_team.shift();
            } else {
            break;
            }
        }
      }
  
      this.in_requests = [];
      }
      
  
      // Part 2: make orders
      this._make_orders(userInputs);
    }
  }
  
export class Warehouse extends Agency {
    constructor(agentNum, config) {
      super(agentNum, config);
      this.inventory = {
        'food': demand(40, 2),
        'drink': demand(40, 2),
        'staff': 9,
      };
  
      this.staff_team = Array.from({ length: this.inventory['staff'] }, () => new Person('staff', 5));
  
      this.action = 'noop';
      this.sleeping = false;
      this._backorder = 0;
      this.strategy = 'bs';
    }
  
    get name() {
      return 'Warehouse';
    }
  
    get reward() {
      return this.curReward;
    }
  
    resetPlayer(T) {
      super.resetPlayer(T);
      this.inventory = {
        'food': demand(40, 2),
        'drink': demand(40, 2),
        'staff': 9,
      };
      this.staff_team = Array.from({ length: this.inventory['staff'] }, () => new Person('staff', 5));
    }
  
    step(_step, userInputs) {
        if (this.mode !== 'human') {
            this._make_decisions_on_requests(userInputs);
        }
        this.receiveItems();
        this._update_life_stats();
      
        // this.curReward = -this._backorder - this.communication;
  
        for (const [name, amount] of Object.entries(this.inventory)) {
            const maxmium = constants.items[name]['max'];
            this.inventory[name] = Math.max(0, Math.min(amount, maxmium));
        }
    }
  
    _update_life_stats() {
      this.consumption = 0;
      let returning_staff = 0;
  
      for (const staff of this.staff_team) {
        if (staff.health <= 0) {
          returning_staff += 1;
          this.staff_team.splice(this.staff_team.indexOf(staff), 1);
          this.inventory['staff'] -= 1;
          this.consumption += 1;
        }
      }
  
      for (const staff of this.staff_team) {
        staff.health += Math.min(5, 1.5 + staff.health);
      }
  
      if (returning_staff > 0) {
        this.out_requests.push(`${returning_staff} staff is returning to the station.`);
      }
    }
  
    _make_decisions_on_requests(userInputs) {
      // Step 1:
      if (self.mode == 'human') {
        userInputs[1]['food'].forEach(([requester, quantity]) => {
            this.AO['food'][this.curTime] = quantity;
            requester.AS['food'][this.curTime + 1] += quantity;
            this.inventory['food'] -= quantity;
        });
        userInputs[1]['drink'].forEach(([requester, quantity]) => {
            this.AO['drink'][this.curTime] = quantity;
            requester.AS['drink'][this.curTime + 1] += quantity;
            this.inventory['drink'] -= quantity;
        });
      } else {
        this.in_requests = this._process_requests();
        const resourceDict = {};

        console.log('warehouse', this.in_requests)
        for (const [requester, quantity, resource] of this.in_requests) {
            if (!(resource in resourceDict)) {
                resourceDict[resource] = [];
            }
        resourceDict[resource].push([requester, parseInt(quantity)]);
        }
  
        for (const [resource, requestsList] of Object.entries(resourceDict)) {
            const totalQuantity = Math.min(this.inventory[resource], requestsList.reduce((acc, [, quantity]) => acc + quantity, 0));
            this.AO[resource][this.curTime] = totalQuantity;
  
        if (this.inventory[resource] >= totalQuantity) {
          for (const [requester, quantity] of requestsList) {
            requester.AS[resource][this.curTime + 1] += quantity;
          }
        } else {
          const averageQuantity = Math.floor(totalQuantity / requestsList.length);
          this.inventory[resource] -= totalQuantity;
  
          for (const [requester] of requestsList) {
            requester.AS[resource][this.curTime + 1] += averageQuantity;
          }
        }
      }
  
      this.in_requests = [];
      }
      
  
      // Step 2:
      this._make_orders(userInputs);
    }
  }
  
export class Shelter extends Agency {
    constructor(agentNum, config) {
      super(agentNum, config);
      this.inventory = {
        'health': demand(10, 2),
        'food': 39,
        'drink': 39,
        'staff': demand(10, 2),
        'death': 0,
      };
  
      this.patients = Array.from({ length: this.inventory['health'] }, () => new Person('injured', 0));
      this.staff_team = Array.from({ length: this.inventory['staff'] }, () => new Person('staff', 5));

      this.base_stock = {
        'food': 30,
        'drink': 30,
        'staff': 15
      };

      this._inventory = 0;
      this._injured = [];
      this.death = 0;
    }
  
    get name() {
      return 'Shelter';
    }
  
    resetPlayer(T) {
      super.resetPlayer(T);
      this.inventory = {
        'health': demand(10, 2),
        'food': 39,
        'drink': 39,
        'staff': demand(20, 2),
        'death': 0,
      };
      this.patients = Array.from({ length: this.inventory['health'] }, () => new Person('injured', 0));
      this.staff_team = Array.from({ length: this.inventory['staff'] }, () => new Person('staff', 5));
      this.base_stock = {
        'food': 30,
        'drink': 30,
        'staff': 15
      };

    }
  
    step(_step, userInputs) {
      this.death = 0;
      this._helped_people = 0;
      this.receiveItems();
  
      const new_arrived_injure = piecewise_function(this.curTime);
      this.inventory['health'] += new_arrived_injure;
  
      for (let i = 0; i < new_arrived_injure; i++) {
        this.patients.push(new Person('injured', 0));
      }
      

      this._make_decisions_on_requests(userInputs);
      this._update_patient_inventory_stats();
      this._update_staff_stats();
  
      this.curReward = -this.death - this.communication;
  
      for (const [name, amount] of Object.entries(this.inventory)) {
        const maxmium = constants.items[name]['max'];
        this.inventory[name] = Math.min(amount, maxmium);
      }
  
      console.log('Day:', _step, this.patients.map(patient => patient.health), this.inventory['health'], this.staff_team.length, this.inventory['food'], this.inventory['drink']);
      console.log(this.patients.map(patient => patient._admitted_days));
    }
  
    _update_patient_inventory_stats() {
      this.consumption = 0;
  
      while (this.patients.length > 0 && this.patients[0].health >= 5) {
        this.patients.shift();
        this.inventory['health'] -= 1;
      }
  
      for (let i = 0; i < Math.min(this.patients.length, this.staff_team.length); i++) {
        const patient = this.patients[i];
        const staff = this.staff_team[i];
  
        if (patient.health < 5) {
          staff.health -= 1;
          this.AO['staff'][this.curTime] += 1;
          this.AO['food'][this.curTime] += 2;
          this.AO['drink'][this.curTime] += 2;
  
          if (this.inventory['food'] > 0) {
            this.inventory['food'] -= 1;
            patient.health += 0.5;
            this.consumption += 1;
            this._helped_people += 1;
          }
  
          if (this.inventory['drink'] > 0) {
            this.inventory['drink'] -= 1;
            patient.health += 0.5;
            this.consumption += 1;
            this._helped_people += 1;
          }
        }
      }
  
      for (let i = 0; i < this.patients.length; i++) {
        if (this.patients[i]._admitted_days >= 5 && this.patients[i].health < 2) {
          this.inventory['death'] += 1;
          this.death += 1;
          this.inventory['health'] -= 1;
        }
      }
  
      this.patients = this.patients.filter(patient => patient._admitted_days < 5);
  
      for (let i = this.staff_team.length; i < this.patients.length; i++) {
        this.AO['staff'][this.curTime] += 1;
        this.AO['food'][this.curTime] += 2;
        this.AO['drink'][this.curTime] += 2;
        this.patients[i]._admitted_days += 1;
      }
      console.log('death', this.AO)
      console.log('death', this.AO['staff'])
      console.log( this.curTime)

      console.log('death', this.death, this.AO['staff'][this.curTime], this.AO['food'][this.curTime], this.AO['drink'][this.curTime]);
    }
  
    _update_staff_stats() {
      let returning_staff = 0;
  
      for (const staff of this.staff_team) {
        if (staff.health <= 0) {
          this.staff_team.splice(this.staff_team.indexOf(staff), 1);
          this.inventory['staff'] -= 1;
          returning_staff += 1;
        } else {
          staff.health -= 0.5;
        }
      }
  
      if (returning_staff > 0) {
        this.out_requests.push(`${returning_staff} staff is returning to station`);
      }
    }
  
    _make_decisions_on_requests(userInputs) {
      // Step 1:
      this.in_requests = this._process_requests();
  
      for (const [requester, resource, quantity] of this.in_requests) {
        if (this.inventory[resource] >= quantity) {
          this.inventory[resource] -= 1;
          requester.inventory[resource] += 1;
        } else if (this.inventory[resource] > 0) {
          this.inventory[resource] -= 1;
          requester.inventory[resource] += 1;
        }
      }
  
      // Clear TODO: do not clear requests that were not satisfied during the current (and past) steps
      this.in_requests = [];
  
      // Step 2:
      this._make_orders(userInputs);
    }
  }
  

function demand(mean = 0, stdDev = 1, distribution = 'normal') {
    let numberInitialPatients;
  
    if (distribution === 'normal') {
      numberInitialPatients = Math.random() * stdDev + mean;
    } else if (distribution === 'poisson') {
      const lambdaParameter = 3.0;
      numberInitialPatients = Math.round(Math.exp(-lambdaParameter) * Math.pow(lambdaParameter, Math.random()));
    } else {
      const low = 10;
      const high = 14;
      numberInitialPatients = Math.random() * (high - low) + low;
    }
  
    return Math.floor(numberInitialPatients);
  }
  
function piecewise_function(x, noise = 'normal') {
    const mean = (x >= 0 && x <= 2) ? -2 * x + 6 : ((x > 2 && x <= 6) ? 2 : (x > 6) ? 0 : 0);
    const noiseValue = (noise === 'normal') ? demand(noise) : 0;
    return mean + noiseValue;
  }

  