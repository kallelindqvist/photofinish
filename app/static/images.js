
let slider = document.getElementById('image_index');
slider.onchange = changeImage;
slider.focus()

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
    var img = document.getElementById('image');
    img.src = '/static/race/' + race + '/image_0001.jpg';
}
