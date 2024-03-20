const strings = [
  'Scaling Up & Transition of Responsibilities',
  'Identify Total Requirements: Identify service delivery requirements for the total operation.',
  'Project Anticipated Costs:  In addition to managing the relief operation, for this exercise, you are being asked to project you anticipated costs of direct and support services by completing a budget development worksheet.',
  'Closing: In these episodes you will be bringing the relief operation to a close. Staff will be released and facilities returned. As you finish each day of the relief operation, ask your facilitator for the next situation report with information about the operation.'
];

var namespace = 'http://' + document.domain + ':' + location.port;
var socket = io(namespace, {path: '/ws/socket.io'});

var grid;
var cols;
var rows;
var width, height;
var w = 13;
var agentX;
var agentY;
var agentDirX;
var agentDirY;
var curX, curY;

// uid from url?
const uid = document.getElementById("uid").value;
var groupID;

var state_map
var time_left
var scoreboard
var numSteps = 0;
var traces = [];
var cost = 0;
var score = 0;
var block = 0;
var targetSteps = 0;

var isGameOver = false;
var gameStarted = false;

var lastKeyEventTime = 0;
var enterEventInterval = 100; // Default settings, but can update this with configurations
var moveEventInterval = 100;
var countPress = 0;
var rescue = 0;
const timeDisplay = document.querySelector('#playtime');
var display_current = document.querySelector('#current-day');
var display_remain = document.querySelector('#remain-day');

var episode = document.getElementById("session").value;
var maxEpisode;
const episodeDisplay = document.getElementById('episode');

var iframe = document.getElementById('frame-qualtrics');
var closeBtn = document.getElementById('close-button');
var chkMap = document.querySelector('#map');
// var chkFull = document.querySelector('#full_falcon');
var chkFull = true;

var numRescuedGreen = 0;
var numRescuedYellow = 0;
var numRescuedRed = 0;
var otherX = [];
var otherY = [];
var roles = [];
var players = [];
var groupSize;
var roleName = '';
// const groupSize = document.getElementById('size').value;
var roomid;
var medicImg;
var engineerImg;
var isFirst = true;
var intervalRecordData;
var intervalEmitSocket;

let socketIOBuffer = [];
let effortHis = [], skillHis = [], efficiencyHis = [];
var tedChart = null;

// waiting room
window.intervalID = -1;
window.ellipses = -1

window.onload = function () {
  showFullView(chkFull);
};

function showElement(ElementId) {
  document.getElementById(ElementId).style.display = 'block';
}

function hideElement(ElementId) {
  document.getElementById(ElementId).style.display = 'none';
}

function showMap(chkMap) {
  if (chkMap.checked) {
    ISMAP = true;
  } else {
    DEBUG = false;
    ISMAP = false;
  }
}

function showFullView(chkFull) {
  DEBUG = false;
  // if (chkFull.checked) {
  //   DEBUG = true;
  // } else {
  //   DEBUG = false;
  // }
}

function sendFailedSocketEmits(){
  if(socketIOBuffer.length>0){
    for(let i=0;i<socketIOBuffer.length; i++){
      emitSocketIO(socketIOBuffer[i].endpoint, socketIOBuffer[i].value);
    }
  }
}

const withTimeout = (onSuccess, onTimeout, timeout) => {
  let called = false;

  const timer = setTimeout(() => {
    if (called) return;
    called = true;
    onTimeout();
  }, timeout);

  return (...args) => {
    if (called) return;
    called = true;
    clearTimeout(timer);
    onSuccess.apply(this, args);
  }
}

function emitSocketIO(endpoint, value){
  try {
    if (socket) {
        socket.emit(endpoint, value, withTimeout(
            () => {},
            () => {
              socketIOBuffer.push({endpoint: endpoint,value: value})
             }, 1000));
    } else {
      socketIOBuffer.push({endpoint: endpoint,value: value})
    }
  }catch (e){
    socketIOBuffer.push({endpoint: endpoint,value: value})
  }
}

socket.on("disconnect", (reason) => {
  sleep(5000).then(() => {
    if (socket.disconnected) {
      alert('The connection is not stable.');
    }
  });
  if (reason === "io server disconnect") {
    // the disconnection was initiated by the server, you need to reconnect manually
    console.log('Io server disconnect')
    socket.connect();
  }
  // else the socket will automatically try to reconnect
});

socket.on("connect_error", () => {
  setTimeout(() => {
    socket.connect();
  }, 1000);
});

socket.on("connect", () => {
  console.log("Is connected: ", socket.connected);
});

socket.on('end_lobby', function (msg) {
  $("#finding_partner").text(
    "We were unable to find you a partner."
  );
  $("#error-exit").show();

  sleep(3000).then(() => { window.location.replace('https://cmu.ca1.qualtrics.com/jfe/form/SV_6hS2CkBKOezDtky'); });

  // Stop trying to join
  clearInterval(window.intervalID);
  clearInterval(window.ellipses);
  window.intervalID = -1;

  // Let parent window (psiturk) know what happened
  window.top.postMessage({ name: "timeout" }, "*");
})

var countWait = 0;
socket.on('waiting', function (data) {
  $('#tab-panel').hide();
  $('#tabgame').hide();
  $('#ready-room').hide();
  $('#lobby').show();
  $('#status').text(data['status'] + " / " + data['max_size']);
  if (parseInt(data['status']) != 0) {
    if (window.intervalID === -1) {
      // Occassionally ping server to try and join
      window.intervalID = setInterval(function () {
        emitSocketIO('ready', {'uid': uid, 'agent_type': "human"});
      }, 1000);
    }
  }
  else if (parseInt(data['status']) === 0) {
    $("#finding_partner").text(
      "We were unable to find you a partner."
    );
    $("#error-exit").show();

    // Stop trying to join
    clearInterval(window.intervalID);
    clearInterval(window.ellipses);
  }
  if (window.lobbyTimeout === -1) {
    // Waiting animation
    window.ellipses = setInterval(function () {
      var e = $("#ellipses").text();
      $("#ellipses").text(".".repeat((e.length + 1) % 10));
    }, 500);
    // Timeout to leave lobby if no-one is found
    window.lobbyTimeout = setTimeout(function () {
      emitSocketIO('leave', {});
    }, lobbyWaitTime)
  }

});

// startWaitTimer();


socket.on('start_game', function (msg) {
  showElement("game-container");
  gameStarted = true;

  episode = msg['episode']
  moveEventInterval = enterEventInterval = 1000 * msg['movement_delay']
  episodeDisplay.textContent = 'Episode: ' + episode;

  scoreboard = msg['scoreboard']
  if (window.intervalID !== -1) {
    clearInterval(window.intervalID);
    window.intervalID = -1;
  }
  if (window.lobbyTimeout !== -1) {
    clearInterval(window.ellipses);
    clearTimeout(window.lobbyTimeout);
    window.lobbyTimeout = -1;
    window.ellipses = -1;
  }
  clearInterval(timeout);

  $('#tab-panel').show();
  $('#tabgame').show();
  $('#lobby').hide();
  $('#ready-room').hide();
  
  // var canvas = createCanvas(width, height); 
  // canvas.parent('sketch-holder');

  socket.on('refresh', function (msg) {
    updateScoreBoard(msg['scoreboard'])
    updateNarratives(msg['current_day'])
    time_left = msg['remaining_time']

    // minutes = (time_left / 60) | 0;
    // seconds = (time_left % 60) | 0;
    // minutes = minutes < 10 ? "0" + minutes : minutes;
    // seconds = seconds < 10 ? "0" + seconds : seconds;
    display_remain.textContent = time_left ; // minutes + ":" + seconds;
    document.getElementById("current-day").innerHTML = msg['current_day'];
    document.getElementById("remain-day").innerHTML = time_left; // minutes + ":" + seconds;
  });


}); //end socket on 'start game'

var isInfoHidden=true;
function setupInformationPanelToggle(){
    $(function() {
        $("#instructionsToggle").click(function () {

            if (!isInfoHidden) {
                $("#tab-panel").slideUp();
                $(this).text("Show commands");
                isInfoHidden = true;
            } else {
                $("#tab-panel").slideDown();
                $(this).text("Hide commands");
                isInfoHidden = false;
            }
        });
    });
}

socket.on('end_episode', function(msg) {
  episode = msg['episode']
    clearInterval(timeout);
    clearInterval(intervalRecordData);
    clearInterval(intervalEmitSocket);
    console.log("Episode over");
    $('#ready-room').show();
    $('#tab-panel').hide();
    $('#tabgame').hide();
});

socket.on('end_game', function(msg) {
  episode = msg['episode']

    clearInterval(timeout);
    clearInterval(intervalRecordData);
    clearInterval(intervalEmitSocket);
  
    console.log("Game over");
    
    //$('#ready-room').show();
    //$('#tab-panel').hide();
    //$('#tabgame').hide();
  
    async function getTotalPoint() {
      const response = await fetch('/points/' + uid + '/');
      const data = await response.json();
      console.log(data)
      $('#tab-panel').hide();
      $('#tabgame').hide();
      $('#notification').show();
  
      var h2 = $('h2', '.notification');
      $("div#notification h2").text(
        "Total points of your team is: " + data
      );
      $("#notification-content").text(
        "You have finished playing the game. You will be forwarded to the post-study section in a few seconds."
      );
    }

    var button = document.getElementById('finish-button');

    sleep(3000).then(() => {
      getTotalPoint();
    });
    sleep(5000).then(() => { button.click(); });

});

function setup() {
  console.log("Client socket: ", socket.id);
  console.log('Client player id:', uid);
  emitSocketIO('join_room', {'uid': uid, 'agent_type': "human"});

  // load images
  var canvas = createCanvas(0, 0);

$('#ready-room').show()
  const ready_button = document.getElementById('ready-button');
  ready_button.addEventListener('click', function(){
    emitSocketIO('ready', {'uid': uid, 'userRole': userRole})
  });
}

setupInformationPanelToggle();

console.log("VERSION 1.6.0");

function updateScoreBoard(scores) {
  document.getElementById('reward').innerHTML = 'Points: ' + scores['reward'].toString();
  document.getElementById('food').innerHTML = 'Food: ' + scores['food'].toString();
  document.getElementById('drink').innerHTML = 'Drink: ' + scores['drink'].toString();
  document.getElementById('staff').innerHTML = 'Staff: ' + scores['staff'].toString();
  document.getElementById('death').innerHTML = 'Death: ' + scores['death'].toString();
  document.getElementById('injured').innerHTML = 'Injured: ' + scores['injured'].toString();
}

function updateNarratives(day) {
  document.getElementById('narrative').innerHTML = strings[day].toString();
  // document.getElementById('food').innerHTML = 'Food: ' + scores['food'].toString();
}

function gameOver() {
  clearInterval(timeout);
  clearInterval(intervalRecordData);
  clearInterval(intervalEmitSocket);

  console.log("Game over");
  
  $('#ready-room').show();
  $('#tab-panel').hide();
  $('#tabgame').hide();


  async function getTotalPoint() {
    const response = await fetch('/points/' + uid + '/');
    const data = await response.json();
    console.log(data)
    $('#tab-panel').hide();
    $('#tabgame').hide();
    $('#notification').show();

    var h2 = $('h2', '.notification');
    $("div#notification h2").text(
      "Total points of your team is: " + data
    );
    $("#notification-content").text(
      "You have finished playing the game. You will be forwarded to the post-study section in a few seconds."
    );
  }

}

function nextEpisode() {
  emitSocketIO('join episode', {'uid': uid, 'episode': episode + 1, 'agent_type': "human"})
}
function writeData(data) {
  const dataOptions = {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  };
  fetch('/game_play', dataOptions);
}

function draw() {
  for (var row = 0; row < rows; row++) {
    for (var col = 0; col < cols; col++){
      temp = new Cell(col, row, w, state_map[row][col]['feature'], state_map[row][col]['revealed'], state_map[row][col]['progress'])

      if (state_map[row][col]['feature'] == "medic"){
        temp.addAgentImage("medic")
      }
      if (state_map[row][col]['feature'] == "engineer"){
        temp.addAgentImage("engineer")
      }
      temp.show()
    }
  }
  if (keyIsDown(13)){
    if (!isGameOver && gameStarted){
      const currentTime = millis();
      if (currentTime - lastKeyEventTime >= enterEventInterval) {
        emitSocketIO('keyEvent', {'uid': uid, 'event': "hold", 'key': 13});
        lastKeyEventTime = currentTime;
      }
    }
  }
}

// Emitting functions
// function keyPressed(){
//   if (!isGameOver && gameStarted) {
//     const currentTime = millis();
//     if (currentTime - lastKeyEventTime >= moveEventInterval) {
//       emitSocketIO('keyEvent', {'uid': uid, 'event': "press", 'key': keyCode});
//       lastKeyEventTime = currentTime;
//     }
//   }
// }

// document.getElementById('next-button').addEventListener('click', function () {
//       // 1. Get user actions
//       const userInputs = {};
//       const userInputBoxes = document.querySelectorAll('.userInput');
//       console.log(`Checking!!!!!`);
 
// });

var timeout;
function startTimer(duration, display) {
  var start = Date.now(),
    diff,
    minutes,
    seconds;

  function timer() {
    diff = duration - (((Date.now() - start) / 1000) | 0);

    if (diff >= 0) {
      minutes = (diff / 60) | 0;
      seconds = (diff % 60) | 0;
      minutes = minutes < 10 ? "0" + minutes : minutes;
      seconds = seconds < 10 ? "0" + seconds : seconds;
      display.textContent = minutes + ":" + seconds;
      document.getElementById("time").innerHTML = minutes + ":" + seconds;
    }
  };
  timer();
  timeout = setInterval(timer, 1000);
}

function startWaitTimer() {
  var start = Date.now(),
    diff,
    minutes,
    seconds;
  var t;
  function timer() {
    diff = lobbyWaitTime / 1000 - (((Date.now() - start) / 1000) | 0);

    if (diff >= 0) {
      minutes = (diff / 60) | 0;
      seconds = (diff % 60) | 0;
      minutes = minutes < 10 ? "0" + minutes : minutes;
      seconds = seconds < 10 ? "0" + seconds : seconds;
      $('#elapsed').text('');
      $('#elapsed').text(minutes + ":" + seconds);
    }
  };
  timer();
  t = setInterval(timer, 1000);
}
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

