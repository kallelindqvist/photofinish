function updateImage() {
    var img = document.getElementById('image');
    img.src = '/camera?' + new Date().getTime();
}

function raceChanged(race) {
    var img = document.getElementById('image');
    img.src = '/static/race/' + race + '/image_0001.jpg';
}
