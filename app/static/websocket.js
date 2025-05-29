var socket = io();

socket.on('cage', function(data) {
    
    document.getElementById('cage_status').innerText=data
})

socket.on('race', function(data) {
    document.getElementById('race_status').innerText=data
    if (data == '🔴 Pågår') {
        var img = document.getElementById('image');
        img.src = '/static/active_race.png';
        document.getElementById('ready_button').disabled = true;
        document.getElementById('race').disabled = true;
        document.getElementById('image_index').disabled = true;
        document.getElementById('stop_button').disabled = true;
    }
    else if(data === '🟡 Inte redo') {
        window.removeEventListener('beforeunload', beforeUnloadHandler);
        window.location = window.location.href
        document.getElementById('ready_button').disabled = false;
        document.getElementById('race').disabled = false;
        document.getElementById('image_index').disabled = false;
        document.getElementById('stop_button').disabled = true;
    }
    else {
        document.getElementById('ready_button').disabled = true;
        document.getElementById('race').disabled = true;
        document.getElementById('image_index').disabled = true;
        document.getElementById('stop_button').disabled = false;
    }
})
