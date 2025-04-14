(function() {
    // Mapping: WASD keys mapped to command names and button IDs.
    const keyMapping = {
      'w': { command: 'forward', buttonId: 'btn-forward' },
      'a': { command: 'left',    buttonId: 'btn-left' },
      's': { command: 'back',    buttonId: 'btn-back' },
      'd': { command: 'right',   buttonId: 'btn-right' }
    };
  
    // Helper function to send a POST request with the given action.
    function sendCommand(command, action) {
      fetch('http://100.96.145.41:8000/' + command, {
        method: 'GET'
      }).catch(err => console.error(`Error sending ${command} ${action}:`, err));
    }
  
    // Object to keep track of active keys so that we only send one "pressed" event per key.
    const activeKeys = {};
  
    // Handle keydown events.
    function keyDownHandler(e) {
      // If the key is repeating (held down), ignore it.
  
      const key = e.key.toLowerCase();
      if (key in keyMapping && !activeKeys[key]) {
        activeKeys[key] = true;
        sendCommand(keyMapping[key].command, 'pressed');
        const btn = document.getElementById(keyMapping[key].buttonId);
        if (btn) btn.classList.add('pressed');
      }
    }
  
    // Handle keyup events.
    function keyUpHandler(e) {
      const key = e.key.toLowerCase();
      if (key in keyMapping && activeKeys[key]) {
        delete activeKeys[key];
        sendCommand(keyMapping[key].command, 'released');
        const btn = document.getElementById(keyMapping[key].buttonId);
        if (btn) btn.classList.remove('pressed');
      }
    }
  
    window.addEventListener('keydown', keyDownHandler);
    window.addEventListener('keyup', keyUpHandler);
  
    // Also attach click and touch event listeners to directional buttons.
    Object.keys(keyMapping).forEach((key) => {
      const { command, buttonId } = keyMapping[key];
      const btn = document.getElementById(buttonId);
      if (btn) {
        btn.addEventListener('mousedown', () => {
          sendCommand(command, 'pressed');
          btn.classList.add('pressed');
        });
        btn.addEventListener('mouseup', () => {
          sendCommand(command, 'released');
          btn.classList.remove('pressed');
        });
        btn.addEventListener('mouseleave', () => {
          sendCommand(command, 'released');
          btn.classList.remove('pressed');
        });
        // For touch support
        btn.addEventListener('touchstart', (e) => {
          e.preventDefault();
          sendCommand(command, 'pressed');
          btn.classList.add('pressed');
        });
        btn.addEventListener('touchend', () => {
          sendCommand(command, 'released');
          btn.classList.remove('pressed');
        });
      }
    });
  })();
  
