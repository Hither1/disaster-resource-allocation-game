import {Shelter, Warehouse, Station} from './objects.js';

let gameEnv;
const gameConfig = {
    size: 10,  // Example size value
    seed: null,  // Example seed value
    length: 20,  // Example length value
    alpha_b: [-0.5, -0.5, -0.5],
    beta_b: [-0.2, -0.2, -0.2],
    demandDistribution: 0,
    demandUp: [16, 8, 6],
    demandLow: [4, 0, 0],
    leadRecItemLow: [2,2,2,4],
    leadRecItemUp: [2,2,2,4],
    leadRecOrderLow: [2,2,2,0],
    leadRecOrderUp: [2,2,2,0]
};

document.getElementById('startButton').addEventListener('click', function () {
    gameEnv = new Env({
        userRole,
        gameConfig
    });

    document.getElementById('userInputs').classList.remove('hidden');
});


const userInputBoxes = document.querySelectorAll('.userInput');
userInputBoxes.forEach(inputBox => {
    inputBox.addEventListener('input', function () {
        if (gameEnv) {
            const input = inputBox.value;
            const inputIdentifier = inputBox.getAttribute('data-input');

            gameEnv.handleUserInput(inputIdentifier, input);

            console.log(`User Input ${inputIdentifier}:`, input);
        } else {
            console.log('Game environment not initialized. Click "Start Game" first.');
        }
    });
});

document.getElementById('nextButton').addEventListener('click', function () {
    if (gameEnv) {
        const [observations, rewards, done, info] = gameEnv.step(userInputs);

        // Log updated observations, rewards, and other information
        console.log('Updated Observations:', observations);
        console.log('Rewards:', rewards);
        console.log('Done:', done);
        console.log('Info:', info);

        userInputs = {};

    } else {
        console.log('Game environment not initialized. Click "Start Game" first.');
    }
});


class Env {
    constructor(user, config) {
      this.config = config;
      console.log(config.alpha_b);
      this.shelter = new Shelter(0, config);
      this.warehouse = new Warehouse(1, config);
      this.station = new Station(2, config);
      if (user === "Shelter") {
        this.shelter.mode = "human";
      } else if (user === "Warehouse") {
        this.warehouse.mode = "human";
      } else if (user === "Station") {
        this.station.mode = "human";
      }
      this.user = user
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
  
    _getReward() {
        death = this.shelter.death;
        consumption = this.shelter.consumption + this.shelter.consumption + this.shelter.consumption;
        communication = this.shelter.communication + this.shelter.communication + this.shelter.communication;

        return death + consumption + communication
    }
  
    step(userInputs) {
      this._step += 1;
      const rewardN = [];
  
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
  
      for (const obj of this.world.objects) {
        if (this._player.distance(obj) < 2 * Math.max(...this._view) && !this.players.includes(obj)) {
          obj.update();
        }
      }
  
      for (const agent of this.players) {
        const r = this._getReward(agent);
        rewardN.push(r);
      }
  
      const done = this._step >= 20;
  
      return [ rewardN, done];
    }
  
    // .
  }

