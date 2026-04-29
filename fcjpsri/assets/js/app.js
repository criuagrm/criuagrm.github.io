const currentPage = document.body.dataset.page;
const menuButton = document.querySelector(".menu-button");
const mobileNav = document.querySelector(".mobile-nav");

document.querySelectorAll("[data-nav]").forEach((link) => {
  if (link.dataset.nav === currentPage) {
    link.classList.add("is-active");
    link.setAttribute("aria-current", "page");
  }
});

if (menuButton && mobileNav) {
  menuButton.addEventListener("click", () => {
    const isOpen = menuButton.getAttribute("aria-expanded") === "true";
    menuButton.setAttribute("aria-expanded", String(!isOpen));
    mobileNav.classList.toggle("is-open", !isOpen);
    menuButton.innerHTML = `<i data-lucide="${isOpen ? "menu" : "x"}"></i>`;
    window.lucide?.createIcons();
  });
}

document.querySelectorAll(".mobile-nav a").forEach((link) => {
  link.addEventListener("click", () => {
    menuButton?.setAttribute("aria-expanded", "false");
    mobileNav?.classList.remove("is-open");
    if (menuButton) {
      menuButton.innerHTML = '<i data-lucide="menu"></i>';
      window.lucide?.createIcons();
    }
  });
});

const year = document.querySelector("[data-year]");
if (year) {
  year.textContent = new Date().getFullYear();
}

window.addEventListener("DOMContentLoaded", () => {
  window.lucide?.createIcons();
});
