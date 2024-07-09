
let slider = document.getElementById('image_index');
slider.onchange = changeImage;
slider.focus()

let updateImageId = null;

function changeImage(e) {
    e.target.disabled = true
    image.src = image.src.replace(/\d{4}.jpg/, e.target.value.padStart(4, 0) + '.jpg')
    e.target.disabled = false
    e.target.focus()
}

function updateImage() {
    var img = document.getElementById('image');
    img.src = '/camera?' + new Date().getTime();
}

function raceChanged(race) {
    if(updateImageId != null) {
        clearInterval(updateImageId);
    }
    if(race === 'preview') {
        updateImageId = setInterval(updateImage, 500);
    }
    else {
        var xhr = new XMLHttpRequest();
        xhr.open('GET', '/image_count?race='+race, true);
        xhr.onreadystatechange = function() {
            if (xhr.status === 200) {
                // Handle successful response
                var count = parseInt(xhr.responseText);
                slider.max = count;
                slider.value = 1;
                slider.focus()
            } else {
                // Handle error or other status codes
                console.error(xhr.status);
            }
        };
        xhr.send();
        var img = document.getElementById('image');
        img.src = '/static/race/' + race + '/image_0001.jpg';
    }
}

function startRace() {
    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/start_race', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.send(JSON.stringify({ race: 'start' }));
}

function stopRace() {
    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/stop_race, true');
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.send(JSON.stringify({ race: 'stop' }));
}