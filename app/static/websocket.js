var socket = io();

socket.on('cage', function(data) {
    if (data == 'open') {
        console.log('Cage is open')
    }
    document.getElementById('cage_status').innerText=data
})

socket.on('race', function(data) {
    document.getElementById('race_status').innerText=data
    if(data === 'Inte redo') {
        const urlParams = new URLSearchParams(window.location.search);
        const training = urlParams.get('training');

        if (training === 'true') {
            startRace();
            var now = new Date().getTime();
            while(new Date().getTime() < now + 500){ /* Do nothing */ }

        }
        window.removeEventListener('beforeunload', beforeUnloadHandler);
        window.location = window.location.href
    }
})
