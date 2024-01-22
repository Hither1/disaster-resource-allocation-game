import {Shelter, Warehouse, Station} from './objects.js';

export function startGame() {
    const config = {
        size: 10,  // Example size value
        seed: null,  // Example seed value
        reward: true,  // Example reward value
        length: 20  // Example length value

    };

    const env = new Env(
        config,
    );

    // Call the reset method to initialize the game environment
    const initialObservations = env.reset();

    
}
document.getElementById('startButton').addEventListener('click', startGame);

class Env {
    constructor(config) {
      

      this.config = config;
      this.shelter = new Shelter('');
      this.warehouse = new Warehouse('');
      this.station = new Station('');
      this.players = [this.shelter, this.warehouse, this.station];
      this.nAgents = this.players.length;
      this.n = this.nAgents;
      this.numTarget = this.players.length;
  
      this.sharedReward = true;

    }
  
    reset() {
      this._episode += 1;
      this._step = 0;
      this.world.reset(seed = hash((this._seed, this._episode)) % (2 ** 31 - 1));
      this.resetCallback(this.world);
      this._updateTime();
  
      const obsN = [];
      for (const agent of this.players) {
        obsN.push(this._getObs(agent));
      }
  
      this.updateOO();
      return obsN;
    }
  
    _getReward() {
      
    }
  

    updateAgentState(agent) {
      if (agent.silent) {
        agent.state.c = new Array(this.dimC).fill(0);
      } else {
        const noise = new Array(agent.action.c.length).fill(0).map(() => Math.random() * agent.cNoise || 0.0);
      }
    }
  
    step(action = null) {
      this._step += 1;
      const obsN = [];
      const rewardN = [];
      const doneN = [];
  
      for (const agent of this.players) {
        agent.step(this._step);
        this.updateAgentState(agent);
      }
  
      const communications = [];
      for (const requester of this.players) {
        if (requester.outRequests.length) {
          for (const request of requester.outRequests) {
            communications.push(requester.outRequests);
  
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
          requester.outRequests = [];
        }
      }
  
      for (const obj of this.world.objects) {
        if (this._player.distance(obj) < 2 * Math.max(...this._view) && !this.players.includes(obj)) {
          obj.update();
        }
      }
  
      for (const agent of this.players) {
        obsN.push(this._getObs(agent));
        const r = this._getReward(agent);
        rewardN.push(r);
      }
  
      const done = this._step >= 20;
  
      return [obsN, rewardN, done];
    }
  
    // .
  }

