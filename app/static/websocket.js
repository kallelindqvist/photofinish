var socket = io();
socket.on('connect', function() {
    console.log("I'm in")
})

socket.on('message', function(data) {
    console.log(data)
})

socket.on('cage', function(data) {
    if (data == 'open') {
        console.log('Cage is open')
    }
    document.getElementById('cage_status').innerText=data
})

socket.on('race', function(data) {
    document.getElementById('race_status').innerText=data
})
