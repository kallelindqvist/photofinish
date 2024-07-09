function updateImage() {
    var img = document.getElementById('image');
    img.src = '/camera?' + new Date().getTime();
}
