const money = new Intl.NumberFormat("en-KE", { style: "currency", currency: "KES", maximumFractionDigits: 0 });
const menuGrid = document.querySelector("#menu-grid");
const categoriesNode = document.querySelector("#categories");
const searchInput = document.querySelector("#menu-search");
const cartDrawer = document.querySelector("#cart-drawer");
const overlay = document.querySelector("#overlay");
const cartContent = document.querySelector("#cart-content");
const cartFooter = document.querySelector("#cart-footer");
const toast = document.querySelector("#toast");

let menuItems = [];
let selectedCategory = "All";
let cart = loadCart();
let toastTimer;

function loadCart() {
  try {
    const stored = JSON.parse(localStorage.getItem("cravy-cart") || "[]");
    return Array.isArray(stored) ? stored.filter((entry) => typeof entry.id === "string" && Number.isInteger(entry.quantity) && entry.quantity > 0 && entry.quantity <= 20) : [];
  } catch {
    return [];
  }
}

function saveCart() {
  localStorage.setItem("cravy-cart", JSON.stringify(cart));
  renderCart();
}

function imageUrl(id, width = 560) {
  return `https://images.unsplash.com/${id}?auto=format&fit=crop&w=${width}&q=80`;
}

function renderMenu() {
  const query = searchInput.value.trim().toLowerCase();
  const visible = menuItems.filter((item) => {
    const matchesCategory = selectedCategory === "All" || item.category === selectedCategory;
    const matchesSearch = `${item.name} ${item.description} ${item.category}`.toLowerCase().includes(query);
    return matchesCategory && matchesSearch;
  });

  menuGrid.innerHTML = visible.length
    ? visible.map((item, index) => `
      <article class="food-card" style="animation-delay:${index * 35}ms">
        <div class="food-photo">
          <img src="${imageUrl(item.image)}" alt="${item.name}" loading="lazy" />
          <span class="food-tag">${item.tag}</span>
        </div>
        <div class="food-details">
          <span class="food-category">${item.category}</span>
          <div class="food-name-line"><span class="food-name">${item.name}</span><span class="food-price">${money.format(item.price)}</span></div>
          <p class="food-description">${item.description}</p>
          <button class="add-button" data-add="${item.id}" aria-label="Add ${item.name} to bag">Add to your bag <span>+</span></button>
        </div>
      </article>`).join("")
    : '<div class="empty-results">Nothing on the menu just yet. Try another search.</div>';
}

function renderCategories() {
  const categories = ["All", ...new Set(menuItems.map((item) => item.category))];
  categoriesNode.innerHTML = categories.map((category) => `
    <button class="category-button${category === selectedCategory ? " active" : ""}" data-category="${category}">${category}</button>
  `).join("");
}

function currentCartLines() {
  return cart.map((entry) => {
    const item = menuItems.find((menuItem) => menuItem.id === entry.id);
    return item ? { ...item, quantity: entry.quantity } : null;
  }).filter(Boolean);
}

function renderCart() {
  const lines = currentCartLines();
  const count = lines.reduce((sum, item) => sum + item.quantity, 0);
  const total = lines.reduce((sum, item) => sum + item.price * item.quantity, 0);
  document.querySelector("#cart-count").textContent = count;
  document.querySelector("#drawer-count").textContent = count ? `(${count})` : "";

  if (!lines.length) {
    cartContent.innerHTML = '<div class="cart-empty"><strong>Your bag is taking a little break.</strong>Let’s find something lovely to fill it.</div>';
    cartFooter.innerHTML = "";
    return;
  }

  cartContent.innerHTML = lines.map((item) => `
    <div class="cart-line">
      <img src="${imageUrl(item.image, 180)}" alt="" />
      <div class="cart-line-info">
        <strong>${item.name}</strong><small>${money.format(item.price)} each</small>
        <div class="quantity-control">
          <button data-quantity="${item.id}" data-change="-1" aria-label="Remove one ${item.name}">−</button>
          <span>${item.quantity}</span>
          <button data-quantity="${item.id}" data-change="1" aria-label="Add one ${item.name}"${item.quantity >= 20 ? " disabled" : ""}>+</button>
        </div>
      </div>
      <span class="cart-line-total">${money.format(item.price * item.quantity)}</span>
    </div>`).join("");

  cartFooter.innerHTML = `
    <div class="subtotal-line"><span>Subtotal</span><span>${money.format(total)}</span></div>
    <p class="cart-footnote">Delivery fee confirmed when we call to say hello.</p>
    <form class="checkout-form" id="checkout-form">
      <h3>Where should we bring it?</h3>
      <div class="checkout-fields">
        <input name="name" autocomplete="name" placeholder="Your name" aria-label="Your name" maxlength="80" required />
        <input name="phone" type="tel" autocomplete="tel" placeholder="Phone number" aria-label="Phone number" maxlength="30" required />
        <input name="address" autocomplete="street-address" placeholder="Delivery address" aria-label="Delivery address" maxlength="240" required />
      </div>
      <fieldset class="payment-options">
        <legend>How would you like to pay?</legend>
        <label><input name="payment" type="radio" value="delivery" checked /> Pay on delivery</label>
        <label><input name="payment" type="radio" value="mpesa" /> M-Pesa prompt</label>
      </fieldset>
      <button class="primary-button" type="submit">Place order · ${money.format(total)} <span>→</span></button>
    </form>`;
}

function setDrawer(open) {
  cartDrawer.classList.toggle("open", open);
  overlay.classList.toggle("open", open);
  document.body.classList.toggle("drawer-open", open);
  cartDrawer.setAttribute("aria-hidden", String(!open));
}

function showToast(message) {
  clearTimeout(toastTimer);
  toast.textContent = message;
  toast.classList.add("show");
  toastTimer = setTimeout(() => toast.classList.remove("show"), 3600);
}

categoriesNode.addEventListener("click", (event) => {
  const button = event.target.closest("[data-category]");
  if (!button) return;
  selectedCategory = button.dataset.category;
  renderCategories();
  renderMenu();
});

searchInput.addEventListener("input", renderMenu);

menuGrid.addEventListener("click", (event) => {
  const button = event.target.closest("[data-add]");
  if (!button) return;
  const existing = cart.find((entry) => entry.id === button.dataset.add);
  if (existing && existing.quantity >= 20) return showToast("You can add up to 20 of each item.");
  if (existing) existing.quantity += 1;
  else cart.push({ id: button.dataset.add, quantity: 1 });
  saveCart();
  showToast(`${menuItems.find((item) => item.id === button.dataset.add).name} added to your bag`);
});

cartContent.addEventListener("click", (event) => {
  const button = event.target.closest("[data-quantity]");
  if (!button) return;
  const entry = cart.find((item) => item.id === button.dataset.quantity);
  if (!entry) return;
  entry.quantity += Number(button.dataset.change);
  if (entry.quantity <= 0) cart = cart.filter((item) => item.id !== button.dataset.quantity);
  saveCart();
});

document.querySelector("#open-cart").addEventListener("click", () => setDrawer(true));
document.querySelector("#close-cart").addEventListener("click", () => setDrawer(false));
overlay.addEventListener("click", () => setDrawer(false));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") setDrawer(false);
});

cartFooter.addEventListener("submit", async (event) => {
  if (event.target.id !== "checkout-form") return;
  event.preventDefault();
  const form = event.target;
  const submitButton = form.querySelector('button[type="submit"]');
  const formData = new FormData(form);
  const isMpesa = formData.get("payment") === "mpesa";
  submitButton.disabled = true;
  submitButton.firstChild.textContent = isMpesa ? "Requesting M-Pesa prompt… " : "Sending your order… ";
  try {
    const response = await fetch(isMpesa ? "/pay" : "/api/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        customer: { name: formData.get("name"), phone: formData.get("phone"), address: formData.get("address") },
        items: cart.map(({ id, quantity }) => ({ id, quantity })),
      }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "We couldn't place that order.");
    if (isMpesa) {
      submitButton.firstChild.textContent = "M-Pesa prompt sent · approve on your phone ";
      showToast(result.payment.customerMessage || `M-Pesa prompt sent. Reference ${result.payment.orderReference}.`);
      return;
    }
    cart = [];
    saveCart();
    setDrawer(false);
    showToast(`Order ${result.order.id} is in! We’ll call to confirm delivery.`);
  } catch (error) {
    showToast(error.message || "Couldn't reach the kitchen. Please try again.");
    submitButton.disabled = false;
    submitButton.firstChild.textContent = isMpesa
      ? `Pay with M-Pesa · ${money.format(currentCartLines().reduce((sum, item) => sum + item.price * item.quantity, 0))} `
      : `Place order · ${money.format(currentCartLines().reduce((sum, item) => sum + item.price * item.quantity, 0))} `;
  }
});

cartFooter.addEventListener("change", (event) => {
  if (event.target.name !== "payment") return;
  const button = cartFooter.querySelector('#checkout-form button[type="submit"]');
  const total = currentCartLines().reduce((sum, item) => sum + item.price * item.quantity, 0);
  button.firstChild.textContent = event.target.value === "mpesa"
    ? `Pay with M-Pesa · ${money.format(total)} `
    : `Place order · ${money.format(total)} `;
});

async function loadMenu() {
  try {
    const response = await fetch("/api/menu");
    if (!response.ok) throw new Error("The menu is taking a moment to load.");
    const data = await response.json();
    menuItems = data.items;
    const menuIds = new Set(menuItems.map((item) => item.id));
    cart = cart.filter((entry) => menuIds.has(entry.id) && entry.quantity <= 20);
    localStorage.setItem("cravy-cart", JSON.stringify(cart));
    renderCategories();
    renderMenu();
    renderCart();
  } catch (error) {
    menuGrid.innerHTML = `<div class="empty-results">${error.message} Please refresh to try again.</div>`;
  }
}

renderCart();
loadMenu();
