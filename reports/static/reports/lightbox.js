/* Лайтбокс для проверки фотографий при модерации.
   Работает и в списке заявок, и в карточке: любой <img data-full="...">
   раскрывается на весь экран. Закрытие — клик или Esc. */
(function () {
  "use strict";

  function build() {
    var box = document.createElement("div");
    box.id = "pandus-lightbox";
    box.innerHTML =
      '<button class="pandus-close" type="button" aria-label="Закрыть">&times;</button>' +
      '<img alt="">' +
      '<div class="pandus-hint">Нажмите в любом месте или Esc, чтобы закрыть</div>';
    document.body.appendChild(box);
    return box;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var thumbs = document.querySelectorAll("img[data-full]");
    if (!thumbs.length) return;

    var box = build();
    var img = box.querySelector("img");

    function open(src) {
      img.src = src;
      box.classList.add("open");
      document.body.style.overflow = "hidden";
    }

    function close() {
      box.classList.remove("open");
      document.body.style.overflow = "";
      img.src = "";
    }

    thumbs.forEach(function (el) {
      el.classList.add("pandus-thumb");
      el.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        open(el.dataset.full);
      });
    });

    box.addEventListener("click", close);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") close();
    });
  });
})();
