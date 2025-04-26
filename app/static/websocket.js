var socket = io();

socket.on('cage', function(data) {
    
    document.getElementById('cage_status').innerText=data
})

socket.on('race', function(data) {
    if (data == 'Pågår') {
        var img = document.getElementById('image');
        img.src = '/static/active_race.png';
    }
    document.getElementById('race_status').innerText=data
    if(data === 'Inte redo') {
        window.removeEventListener('beforeunload', beforeUnloadHandler);
        window.location = window.location.href
    }
})
