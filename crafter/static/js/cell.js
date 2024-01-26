var DEBUG = false;
var ISMAP = false;
var color_dict = {
  'door': [128, 0, 128],
  'yellow': [255, 215, 0],
  'green': [0, 128, 0],
  'red': [255, 0, 0],
  'rubble': [150, 75, 0]
};

function Cell(i, j, w, goal, revealed, progress) {
  this.i = i;
  this.j = j;
  this.x = i * w;
  this.y = j * w;
  this.w = w;
  this.revealed = revealed;
  this.progress = progress;
  this.goal = goal;
}

Cell.prototype.show = function () {
  stroke(192,192,192);
  noFill();
  rect(this.x, this.y, this.w, this.w);
  if (this.revealed == 1) {
    fill(127);

    if (this.goal == 'wall') {
      fill(128, 128, 128);
      rect(this.x, this.y, this.w, this.w);
    }

    else if (this.goal == '') {
      fill(205, 231, 239);
      rect(this.x, this.y, this.w, this.w);
    }

    else if (this.goal == 'medic' | this.goal == 'engineer') {

    }

    else {
      tile_color = color_dict[this.goal];
      fill(tile_color[0], tile_color[1], tile_color[2], 255 - Math.round(this.progress * 255));
      rect(this.x, this.y, (1-this.progress)*this.w, this.w);
      noFill();
      //fill(205, 231, 239);
      rect(this.x + (1 - this.progress)* this.w, this.y, this.progress*this.w, this.w);
      //if (this.progress > 0) {
      //  textAlign(LEFT, BOTTOM);
      //  fill('black');
      //  textSize(8)
      //  text(Math.round(this.progress * 100), this.x + this.w * 0.2, this.y + this.w, this.w);
      //}
    }
  }

  
  // Add borders
  if (this.goal == 'borders') {
    // fill(200,200,200,127);
    fill(173,216,230,127);
    //fill(250, 250, 250, 127);
    
    rect(this.x, this.y, this.w, this.w);
  }
  if (DEBUG) {

    if (this.goal == 'wall') {
      fill(128, 128, 128);
      rect(this.x, this.y, this.w, this.w);
    }

    else if (this.goal == 'door') {
      fill(128, 0, 128);
      rect(this.x, this.y, this.w, this.w);
    }
    else if (this.goal == 'yellow') {
      fill(255,215,0);
      rect(this.x, this.y, this.w, this.w);
    } 
    else if (this.goal == 'green') {
      fill(0, 128, 0);
      rect(this.x, this.y, this.w, this.w);
    }
    else if (this.goal == 'blue') {
      fill(0, 0, 255);
      rect(this.x, this.y, this.w, this.w);
    }
    else if (this.goal == 'red') {
      fill(255, 0, 0);
      rect(this.x, this.y, this.w, this.w);
    }
    else if (this.goal == 'rubble') {
      fill(182,182,182);
      rect(this.x, this.y, this.w, this.w);
      textAlign(LEFT, TOP);
      fill(0);
      text("X", this.x + this.w * 0.15, this.y + this.w * 0.9, this.w); 
    }

  }
  if (ISMAP) {

    if (this.goal == 'wall') {
      fill(128, 128, 128);
      rect(this.x, this.y, this.w, this.w);
    }

    else if (this.goal == 'door') {
      fill(128, 0, 128);
      rect(this.x, this.y, this.w, this.w);
    }
  }
}

Cell.prototype.addAgent = function () {
  this.agent = true;
  fill(255,83,73);
  ellipse(this.x + this.w * 0.5, this.y + this.w * 0.5, this.w);
}

Cell.prototype.addMyAgent = function (agent_id) {
  this.agent = true;
  // fill(255,83,73);
  fill(128,0,0);
  ellipse(this.x + this.w * 0.5, this.y + this.w * 0.5, this.w);
  textAlign(CENTER);
  fill(255);
  text(agent_id, this.x + this.w * 0.1, this.y + this.w * 0.8, this.w); 
}

Cell.prototype.addAgentImage = function (roleName) {
  this.agent = true;
  if (roleName=='medic'){
    image(medicImg, this.x, this.y, 15, 15)
  }else if (roleName=='engineer'){
    image(engineerImg, this.x, this.y, 15, 15)

  }
  
}


Cell.prototype.addOtherAgentImg = function (roleName) {
  // fill(255,63,47);
  // fill(105,105,105);
  if (roleName=='medic'){
    image(medicImg, this.x, this.y, 15, 15)
  }else if (roleName=='engineer'){
    image(engineerImg, this.x, this.y, 15, 15)
  }
}

Cell.prototype.markAsVisitedbyAgent = function () {
  this.agent = false;
  //fill(0,0,255); //change back
  fill(205, 231, 239);
  // fill(255,83,73);
  ellipse(this.x + this.w * 0.5, this.y + this.w * 0.5,this.w/3);
  // textAlign(CENTER);
  // fill(255);
  // text(val, this.x + this.w * 0.1, this.y + this.w * 0.8, this.w); 
}

Cell.prototype.markAsVisitedbyRole = function (roleName) {
  this.agent = false;
  if (roleName=='medic'){
    fill(229,83,0); 
    ellipse(this.x + this.w * 0.5, this.y + this.w * 0.5, this.w/2);
  }else if (roleName=='engineer'){
    fill(0,0,255); //change back
    ellipse(this.x + this.w * 0.5, this.y + this.w * 0.5, this.w/2);
  }
    
  // fill(255,83,73);
  
  // textAlign(CENTER);
  // fill(255);
  // text(val, this.x + this.w * 0.1, this.y + this.w * 0.8, this.w); 
}

Cell.prototype.markAsVisitedbyEngineer = function () {
  this.agent = false;
  fill(255,215,0); 
  ellipse(this.x + this.w * 0.5, this.y + this.w * 0.5, this.w/3);
}



Cell.prototype.drawFoV = function () {
  fill(250,250,250,63);
  rect(this.x, this.y, this.w, this.w);
}

Cell.prototype.addText = function (val){
  textAlign(CENTER);
  fill(0);
  text(val, this.x + this.w * 0.5, this.y + this.w - 15);
}

Cell.prototype.contains = function (x, y) {
  return (x > this.x && x < this.x + this.w && y > this.y && y < this.y + this.w);
}

Cell.prototype.reveal = function () {
  this.revealed = 1;
}