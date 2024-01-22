import {Shelter, Warehouse, Station} from './objects.js';

let gameEnv;
const gameConfig = {
    size: 10,  // Example size value
    seed: null,  // Example seed value
    length: 20,  // Example length value
    alpha_b: [-0.5, -0.5, -0.5],
    betta_b: [-0.2, -0.2, -0.2],
    demandDistribution: 0,
    demandUp: [16, 8, 6],
    demandLow: [4, 0, 0],
    leadRecItemLow: [2,2,2,4],
    leadRecItemUp: [2,2,2,4],
    leadRecOrderLow: [2,2,2,0],
    leadRecOrderUp: [2,2,2,0]
};

document.getElementById('startButton').addEventListener('click', function () {
    gameEnv = new Env(
        userRole,
        gameConfig
    );

    const startButton = document.getElementById('startButton');
    startButton.style.display = 'none';

    const startMsg = document.getElementById('startMsg');
    startMsg.style.display = 'none';

    document.getElementById('userInputs').classList.remove('hidden');
});


document.getElementById('nextButton').addEventListener('click', function () {
    if (gameEnv) {
        // 1. Get user actions
        userInputs = {};

        const userInputBoxes = document.querySelectorAll('.userInput');
        userInputBoxes.forEach(inputBox => {
            inputBox.addEventListener('input', function () {
            if (gameEnv) {
                const input = inputBox.value;
                const inputIdentifier = inputBox.getAttribute('data-input');

                if (!isNaN(inputValue)) {
                    userInputs[inputType] = inputValue;
                }

            console.log(`User Input ${inputIdentifier}:`, input);
            } else {
                console.log('Game environment not initialized. Click "Start Game" first.');
            }
            });
        });

        // 2. Run env step
        const [reward, user_food, user_drink, user_staff, done] = gameEnv.step(userInputs);

        document.getElementById('day').textContent = this._step;
        document.getElementById('goal').textContent = reward;
        document.getElementById('food').textContent = user_food;
        document.getElementById('drink').textContent = user_drink;
        document.getElementById('staff').textContent = user_staff;

        // 3. If finished
        if (done) {
            window.location.href = 'done.html';
          }

    } else {
        console.log('Game environment not initialized. Click "Start Game" first.');
    }
});


class Env {
    constructor(user, config) {
      this.config = config;
      this.shelter = new Shelter(0, config);
      this.warehouse = new Warehouse(1, config);
      this.station = new Station(2, config);
      if (user === "Shelter") {
        this.user = this.shelter
        this.shelter.mode = "human";
      } else if (user === "Warehouse") {
        this.user = this.warehouse
        this.warehouse.mode = "human";
      } else if (user === "Station") {
        this.user = this.station
        this.station.mode = "human";
      }
      this.user_name = user
      this.players = [this.shelter, this.warehouse, this.station];
      this.nAgents = this.players.length;
      this.n = this.nAgents;
      this.numTarget = this.players.length;
  
      this.sharedReward = true;
      this._step = 0;

    }
  
    reset() {
      this._episode += 1;
      this._step = 0;
      this.updateOO();

    }
  
    getReward() {
        death = this.shelter.death;
        consumption = this.shelter.consumption + this.shelter.consumption + this.shelter.consumption;
        communication = this.shelter.communication + this.shelter.communication + this.shelter.communication;

        return death + consumption + communication
    }
  
    step(userInputs) {
      this._step += 1;
      const rewardN = [];
      userInputs = this.process_userInputs(userInputs);
  
      for (const agent of this.players) {
        if (agent.name === self.user){
            agent.step(this._step, userInputs);
        } else {
            agent.step(this._step);
        }
      }
  
      const communications = [];
      for (const requester of this.players) {
        if (requester.out_requests.length) {
          for (const request of requester.out_requests) {
            communications.push(requester.out_requests);
  
            if ('return' in request) {
              this.world.station.inventory.staff += parseInt(request.match(/\d+/)[0]);
            } else {
              const requestee = request.split('->')[1].split(':')[0];
              if (requestee === 'Warehouse') {
                this.world.warehouse.inRequests.push([requester, request.split(': ')[1]]);
              } else if (requestee === 'Station') {
                this.world.station.inRequests.push([requester, request.split(': ')[1]]);
              } else {
                this.world.shelter.inRequests.push([requester, request.split(': ')[1]]);
              }
            }
          }
          requester.out_requests = [];
        }
      }
  
  
    //   for (const agent of this.players) {
    //     const r = this._getReward(agent);
    //     rewardN.push(r);
    //   }
      rewardN = this.getReward()
      const done = this._step >= 20;
  
      return [rewardN, this.user.inventory['food'], this.user.inventory['drink'], this.user.inventory['staff'], done];
    }
    
    process_userInputs(userInputs) {
        const to_return = [{'food': 0, 'drink': 0, 'staff': 0}, {'food': [], 'drink': [], 'staff': []}];
        const resources = ['food', 'drink', 'staff'];
        const requesters = ['food', 'drink', 'staff'];
        Object.entries(userInputs).forEach(([key, value]) => {
            if (key.includes('request')) { // request

                for (const resource of resources) {
                    if (key.includes(resource)) {
                    to_return[0][resource] += value;
                    }
                }
                
            } else { // send

                for (const requester of requesters) {
                    if (key.includes(requester)) {
                    to_return[1][requester].push([requester, value]);
                    }
                }
            }
          });
        return to_return;
    }
    // .
  }

