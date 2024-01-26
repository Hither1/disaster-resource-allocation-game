import {Shelter, Warehouse, Station} from './objects.js';

const strings = [
    'Initial Response: You knew it was coming. This episode is the start of a disaster relief operation. Your team will be managing the initial response. You will receive a separate situation report and task assignment sheet.',
    'Scaling Up & Transition of Responsibilities',
    'Identify Total Requirements: Identify service delivery requirements for the total operation.',
    'Project Anticipated Costs:  In addition to managing the relief operation, for this exercise, you are being asked to project you anticipated costs of direct and support services by completing a budget development worksheet.',
    'Closing: In these episodes you will be bringing the relief operation to a close. Staff will be released and facilities returned. As you finish each day of the relief operation, ask your facilitator for the next situation report with information about the operation.'
];

let gameEnv;
let gameConfig = {
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

function setup() {
  // showFullView(chkFull);
  console.log("Client socket: ", socket.id);
  console.log('Client player id:', uid);
  emitSocketIO('join_room', {'uid': uid, 'agent_type': "human"});

  // load images
  // medicImg = loadImage("https://cdn-icons.flaticon.com/png/512/2371/premium/2371329.png?token=exp=1646427991~hmac=66091d24f0f77d7e5a90a48fd33dc6d9");
  medicImg = loadImage("https://raw.githubusercontent.com/ngocntkt/visualization-map/master/aid.png");
  engineerImg = loadImage("https://raw.githubusercontent.com/ngocntkt/visualization-map/master/hammer2.png");

  // episodeDisplay.textContent = 'Episode: ' + episode;
  var canvas = createCanvas(0, 0);

  $('#ready-room').show()
  const ready_button = document.getElementById('ready-button');
  ready_button.addEventListener('click', function(){
    emitSocketIO('ready', {'uid': uid})
  });
}

document.getElementById('startButton').addEventListener('click', function () {
  emitSocketIO('ready', {'uid': uid});
    // gameConfig = updateConfig(gameConfig);
    // gameEnv = new Env(
    //     userRole,
    //     gameConfig
    // );

    // const startButton = document.getElementById('startButton');
    // startButton.style.display = 'none';

    // const startMsg = document.getElementById('startMsg');
    // startMsg.style.display = 'none';

    // document.getElementById('userInputs').classList.remove('hidden');
});


document.getElementById('nextButton').addEventListener('click', function () {
    if (gameEnv) {
        // 1. Get user actions
        const userInputs = {};

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
      this.shelter.resetPlayer(100);
      this.warehouse.resetPlayer(100);
      this.station.resetPlayer(100);
    console.log('user', user);
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
      this.shelter.resetPlayer(100);
      this.warehouse.resetPlayer(100);
      this.station.resetPlayer(100);

    }
  
    getReward() {
        death = this.shelter.death;
        consumption = this.shelter.consumption + this.shelter.consumption + this.shelter.consumption;
        communication = this.shelter.communication + this.shelter.communication + this.shelter.communication;

        return 10 * death + consumption + communication
    }
  
    step(userInputs) {
      this._step += 1;

      // Display narratives
      const dynamicContentElement = document.getElementById('dynamicContent');
      console.log('checking my strings', strings, this._step, strings[this._step-1])
      if (dynamicContentElement) {
            dynamicContentElement.innerHTML = `<p>${strings[this._step-1]}</p>`;
      } else {
        console.error('Element with ID "dynamicContent" not found.');
      }

      const rewardN = [];
      userInputs = this.process_userInputs(userInputs);
  
      for (const agent of this.players) {
            agent.step(this._step, userInputs);
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
                this.world.warehouse.in_requests.push([requester, request.split(': ')[1]]);
              } else if (requestee === 'Station') {
                this.world.station.in_requests.push([requester, request.split(': ')[1]]);
              } else {
                this.world.shelter.in_requests.push([requester, request.split(': ')[1]]);
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

function buildActionList(config) {
    const aDiv = 1; // difference in the action list
    let actions;

    if (config.fixedAction) {
        actions = Array.from({ length: Math.ceil((config.actionMax + 1) / aDiv) }, (_, i) => i * aDiv); // If you put the second argument =11, creates an action list from 0..xx
    } else {
        actions = Array.from({ length: Math.ceil((config.actionUp - config.actionLow + 1) / aDiv) }, (_, i) => config.actionLow + i * aDiv);
    }

    return actions;
}


function updateConfig(config) {
    config.actionList = buildActionList(config); // The list of the available actions
    config.actionListLen = config.actionList.length; // the length of the action list
    
    // set_optimal(config)
    config.f = [config.f1, config.f2, config.f3, config.f4]; // [6.4, 2.88, 2.08, 0.8]

    config.actionListLen = config.actionList.length;
    if (config.demandDistribution === 0) {
        config.actionListOpt = Array.from({ length: Math.max(config.actionUp * 30 + 1, 3 * config.f.reduce((acc, val) => acc + val, 0)) }, (_, i) => i);
    } else {
        config.actionListOpt = Array.from({ length: Math.max(config.actionUp * 30 + 1, 7 * config.f.reduce((acc, val) => acc + val, 0)) }, (_, i) => i);
    }
    config.actionListLenOpt = config.actionListOpt.length;
    config.agentTypes = ['dnn', 'dnn', 'dnn', 'dnn'];
    config.saveFigInt = [config.saveFigIntLow, config.saveFigIntUp];

    // if (config.gameConfig === 0) {
    //     config.NoAgent = Math.min(config.NoAgent, config.agentTypes.length);
    //     config.agentTypes = [config.agent_type1, config.agent_type2, config.agent_type3, config.agent_type4];
    // } else {
    //     config.NoAgent = 4;
    //     setAgentType(config); // set the agent brain types according to ifFourDNNtrain, ...
    // }

    config.c_h = [config.ch1, config.ch2, config.ch3, config.ch4];
    config.c_p = [config.cp1, config.cp2, config.cp3, config.cp4];

    // config.stateDim = getStateDim(config); // Number of elements in the state description - Depends on ifUseASAO
    // Math.seedrandom(config.seed);
    // setSavedDimentionPerBrain(config); // set the parameters of pre_trained model.
    // fillnodes(config);
    // getAuxiliaryLeadtimeInitialValues(config);
    // fixLeadTimeManufacturer(config);
    // fillLeadtimeInitialValues(config);
    // setStermanParameters(config);

    return config;
}


