// Present the backend-priced cart and saved order through authenticated REST calls.
// Persist only the original checkout attempt for safe receipt lookup and explicit replay;
// never automatically repeat a POST whose outcome could already be durable.
import { setStatus } from "./ui.js";
import { customerToken, customerRequest, customerError } from "./customer-session.js";

const ATTEMPT_KEY = "food4thought.customer.checkout.attempt";
const el = id => document.getElementById(id);
const cartStatus = el("cart-status");
const cartError = el("cart-error");
const cartContent = el("cart-content");
const cartItems = el("cart-items");
const createButton = el("create-cart");
const refreshButton = el("refresh-cart");
const clearButton = el("clear-cart");
const checkoutButton = el("checkout-button");
const orderPanel = el("order-confirmation");
const recoveryPanel = el("checkout-help");
const recoveryStatus = el("checkout-status");
const checkButton = el("check-order");
const retryButton = el("retry-checkout");

let cart = null;
let busy = false;
let attempt = readAttempt();

function readAttempt() {
  try {
    const value = JSON.parse(sessionStorage.getItem(ATTEMPT_KEY));
    if (value && typeof value.customer_id === "string" &&
        typeof value.cart_id === "string" && Number.isSafeInteger(value.cart_revision) &&
        value.cart_revision >= 0) return value;
  } catch { /* A stale or malformed tab value is not an authorization credential. */ }
  sessionStorage.removeItem(ATTEMPT_KEY);
  return null;
}

function saveAttempt(value) {
  attempt = value;
  sessionStorage.setItem(ATTEMPT_KEY, JSON.stringify(value));
}

function clearAttempt() {
  attempt = null;
  sessionStorage.removeItem(ATTEMPT_KEY);
  recoveryPanel.hidden = true;
}

function message(element, text) {
  element.textContent = text;
}

function validCart(value) {
  return value && typeof value.id === "string" && typeof value.customer_id === "string" &&
    Number.isSafeInteger(value.revision) && Array.isArray(value.items) &&
    typeof value.subtotal === "string" && typeof value.total === "string";
}

function validOrder(value) {
  return value && typeof value.id === "string" && typeof value.restaurant_name === "string" &&
    typeof value.total === "string" && Array.isArray(value.items) &&
    typeof value.source_cart_id === "string" && Number.isSafeInteger(value.source_cart_revision);
}

function updateControls() {
  const disabled = busy || Boolean(attempt);
  refreshButton.disabled = busy;
  createButton.disabled = disabled;
  clearButton.disabled = disabled || !cart || cart.items.length === 0;
  checkoutButton.disabled = disabled || !cart || cart.items.length === 0;
  for (const button of cartItems.querySelectorAll("button, input")) button.disabled = disabled;
  checkButton.disabled = busy;
  retryButton.disabled = busy;
}

function setBusy(value) {
  busy = value;
  cartContent.setAttribute("aria-busy", String(value));
  updateControls();
}

function renderOrder(order) {
  if (!validOrder(order)) {
    message(cartError, "The saved order response was unexpected. Check order status before trying again.");
    return;
  }
  orderPanel.hidden = false;
  el("order-state").hidden = order.status !== "placed";
  el("order-id").textContent = order.id;
  el("order-restaurant").textContent = order.restaurant_name;
  el("order-total").textContent = `$${order.total}`;
  const list = el("order-items");
  list.replaceChildren();
  for (const item of order.items) {
    const row = document.createElement("li");
    row.textContent = `${item.name} × ${item.quantity} — $${item.line_total}`;
    list.append(row);
  }
}

function showRecovery(text, canRetry = false, retryLabel = "Retry original checkout") {
  recoveryPanel.hidden = false;
  setStatus(recoveryStatus, text, "warning");
  retryButton.hidden = !canRetry;
  retryButton.textContent = retryLabel;
  updateControls();
}

function renderCart(view) {
  cart = view;
  cartContent.hidden = false;
  createButton.hidden = true;
  cartItems.replaceChildren();
  el("cart-subtotal").textContent = `$${view.subtotal}`;
  el("cart-total").textContent = `$${view.total}`;
  for (const line of view.items) {
      const item = document.createElement("li");
      const details = document.createElement("div");
      const name = document.createElement("strong");
      name.textContent = line.name;
      const price = document.createElement("p");
      price.textContent = `$${line.unit_price} each · Line total $${line.line_total}`;
      details.className = "cart-line-details";
      details.append(name, price);
      if (!line.available) {
        const unavailable = document.createElement("p");
        unavailable.className = "status error";
        unavailable.textContent = "Unavailable — remove this item before checkout.";
        details.append(unavailable);
      }
      const form = document.createElement("form");
      form.className = "cart-line-controls";
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "number";
      input.min = "1";
      input.step = "1";
      input.required = true;
      input.value = String(line.quantity);
      input.id = `quantity-${view.items.indexOf(line)}`;
      label.className = "visually-hidden";
      label.htmlFor = input.id;
      label.textContent = `Quantity for ${line.name}`;
      const update = document.createElement("button");
      update.type = "submit";
      update.textContent = "Update quantity";
      update.setAttribute("aria-label", `Update quantity for ${line.name}`);
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "Remove";
      remove.setAttribute("aria-label", `Remove ${line.name}`);
      form.append(label, input, update, remove);
      form.addEventListener("submit", event => {
        event.preventDefault();
        const raw = input.value;
        if (!/^[1-9][0-9]*$/.test(raw) || !Number.isSafeInteger(Number(raw))) {
          message(cartError, "Quantity must be a positive whole number.");
          return;
        }
        void mutateCart("PATCH", `/customers/me/cart/items/${encodeURIComponent(line.item_id)}`,
          { quantity: Number(raw) }, "Quantity updated.");
      });
      remove.addEventListener("click", () =>
        void mutateCart("DELETE", `/customers/me/cart/items/${encodeURIComponent(line.item_id)}`,
          undefined, "Item removed."));
      item.append(details, form);
      cartItems.append(item);
  }
  updateControls();
}

async function refreshCart({ reconcile = true } = {}) {
  if (!customerToken()) {
    cart = null;
    cartContent.hidden = true;
    createButton.hidden = true;
    setStatus(cartStatus, "Sign in from My account to view your cart.", "warning");
    return;
  }
  setBusy(true);
  // A failed read must not leave stale totals or a stale cart revision actionable.
  cart = null;
  cartContent.hidden = true;
  createButton.hidden = true;
  setStatus(cartStatus, "Loading cart…", "loading");
  message(cartError, "");
  try {
    const response = await customerRequest("/customers/me/cart");
    if (response.status === 404) {
      // An attempt belongs to the customer who made it. A new account may have
      // no cart, so check identity before preserving an earlier tab's attempt.
      if (attempt) {
        const profile = await customerRequest("/customers/me");
        if (profile.ok && typeof profile.body?.id === "string" &&
            profile.body.id !== attempt.customer_id) clearAttempt();
      }
      cart = null;
      cartContent.hidden = true;
      createButton.hidden = Boolean(attempt);
      setStatus(cartStatus, "No cart yet. Create one or add an item from a restaurant menu.", "empty");
    } else if (!response.ok) {
      setStatus(cartStatus, "");
      message(cartError, customerError(response.status, response.body));
      if (response.status === 401) orderPanel.hidden = true;
      // Do not return: a pending checkout's saved receipt may still be
      // available through order history when this cart endpoint is broken.
    } else if (validCart(response.body)) {
      if (attempt && attempt.customer_id !== response.body.customer_id) clearAttempt();
      renderCart(response.body);
      const hasItems = response.body.items.length > 0;
      setStatus(cartStatus, hasItems ? "Cart loaded with current menu prices." : "Your cart is empty.",
        hasItems ? "" : "empty");
      if (!attempt && response.body.checkout_order_id) {
        saveAttempt({ customer_id: response.body.customer_id,
          cart_id: response.body.id, cart_revision: response.body.revision });
      }
    } else {
      message(cartError, "Unexpected cart response. Refresh before changing anything.");
    }
  } catch {
    setStatus(cartStatus, "");
    message(cartError, "Could not confirm the current cart. Check your connection and refresh before editing.");
  } finally {
    setBusy(false);
  }
  if (attempt && reconcile) await checkOrderStatus();
}

async function checkOrderStatus() {
  if (!attempt || busy) return;
  setBusy(true);
  showRecovery("Checking saved orders for the original cart and revision…");
  try {
    const response = await customerRequest("/customers/me/orders");
    if (!response.ok) {
      showRecovery(`Could not verify the order. ${customerError(response.status, response.body)} No checkout was retried.`);
      return;
    }
    if (!Array.isArray(response.body)) {
      showRecovery("Order history was unexpected. No checkout was retried.");
      return;
    }
    const saved = response.body.find(order => validOrder(order) &&
      order.source_cart_id === attempt.cart_id &&
      order.source_cart_revision === attempt.cart_revision);
    if (saved) {
      renderOrder(saved);
      if (cart && cart.id === attempt.cart_id && cart.revision === attempt.cart_revision) {
        showRecovery("Found a saved order. The original cart still needs checkout recovery.",
          true, "Complete cart reset");
      } else if (cart) {
        clearAttempt();
        // A saved receipt is authoritative even when its response was lost.
        setStatus(cartStatus, "Found your saved order. No second order was submitted.", "success");
        showRecovery("Found a saved order. No checkout retry is needed.");
      } else {
        // The receipt is durable, but without a cart read we cannot tell if
        // the purchased revision still needs a conditional reset.
        showRecovery("Found your saved order, but cannot confirm the cart reset. Refresh cart to verify it before making changes.");
      }
    } else if (!cart) {
      showRecovery("No saved order was found, but the cart cannot be verified. Refresh cart before trying the original checkout again.");
    } else if (cart.id !== attempt.cart_id || cart.revision !== attempt.cart_revision) {
      clearAttempt();
      showRecovery("Your cart changed. Review the current items and total before placing an order.");
    } else {
      showRecovery("No saved order was found for this attempt. Recheck the status or explicitly retry the same cart revision; it cannot create a second order for that revision.", true);
    }
  } catch {
    showRecovery("Could not check saved orders. No checkout was retried; check your connection and try again.");
  } finally {
    setBusy(false);
  }
}

async function mutateCart(method, path, payload, success) {
  if (busy || attempt) return;
  setBusy(true);
  message(cartError, "");
  setStatus(cartStatus, "Saving cart…", "loading");
  try {
    const response = await customerRequest(path, { method, payload });
    if (!response.ok) {
      message(cartError, customerError(response.status, response.body, method === "PATCH"));
      setStatus(cartStatus, "");
      if (response.status === 409 && response.body?.detail === "Cart checkout recovery required") {
        // A saved order prevents normal cart writes until its original attempt is replayed.
        saveAttempt({ customer_id: cart.customer_id, cart_id: cart.id, cart_revision: cart.revision });
        showRecovery("Checkout recovery is required before any cart edits.");
      }
      return;
    }
    if (!validCart(response.body)) {
      message(cartError, "Could not confirm the cart update. Refresh before trying again.");
      cartContent.hidden = true;
      return;
    }
    renderCart(response.body);
    setStatus(cartStatus, success, "success");
  } catch {
    message(cartError, "Could not confirm the cart update. Refresh before trying again; do not repeat an unconfirmed change.");
    cartContent.hidden = true;
  } finally {
    setBusy(false);
  }
}

async function createCart() {
  if (busy || attempt) return;
  setBusy(true);
  setStatus(cartStatus, "Creating cart…", "loading");
  message(cartError, "");
  try {
    const response = await customerRequest("/customers/me/cart", { method: "PUT" });
    if (!response.ok) {
      message(cartError, customerError(response.status, response.body));
      return;
    }
    if (!validCart(response.body)) {
      message(cartError, "Could not confirm cart creation. Refresh to check it.");
      return;
    }
    renderCart(response.body);
    setStatus(cartStatus, "Cart ready.", "success");
  } catch {
    message(cartError, "Could not confirm cart creation. Refresh before trying again.");
  } finally {
    setBusy(false);
  }
}

async function doCheckout() {
  if (busy || !attempt) return;
  const original = { ...attempt };
  let revisionChanged = false;
  setBusy(true);
  message(cartError, "");
  setStatus(cartStatus, "Placing order…", "loading");
  try {
    const response = await customerRequest("/customers/me/checkout", {
      method: "POST",
      payload: { cart_id: original.cart_id, cart_revision: original.cart_revision },
    });
    if ((response.status === 200 || response.status === 201) &&
        validOrder(response.body?.order) &&
        typeof response.body.cart_reset_pending === "boolean") {
      renderOrder(response.body.order);
      setStatus(cartStatus, "Your saved order was confirmed.", "success");
      if (response.body.cart_reset_pending) {
        showRecovery("Order saved. The cart reset is pending; use Complete cart reset to replay this same purchase.", true, "Complete cart reset");
      } else {
        clearAttempt();
        // Keep the saved receipt visible while fetching the newly reset cart.
        await refreshCart({ reconcile: false });
        setStatus(cartStatus, "Your saved order was confirmed.", "success");
      }
      return;
    }
    if (response.status === 409 && response.body?.detail === "Cart revision changed") {
      // Another session changed the cart. Hide the obsolete quote until a
      // fresh GET succeeds; the customer must review it before a new checkout.
      clearAttempt();
      cart = null;
      cartContent.hidden = true;
      revisionChanged = true;
    } else if (response.status >= 400 && response.status < 500) {
      clearAttempt();
      setStatus(cartStatus, "");
      message(cartError, customerError(response.status, response.body));
      return;
    } else {
      showRecovery("Checkout outcome is uncertain. Checking order history before any manual retry…");
    }
  } catch {
    showRecovery("Checkout response was lost or timed out. Checking order history; no automatic repeat will be made.");
  } finally {
    setBusy(false);
  }
  if (revisionChanged) {
    await refreshCart({ reconcile: false });
    if (cart) {
      message(cartStatus, "Cart changed in another session. Review the updated cart and total before placing an order.");
    } else {
      message(cartError, "Cart revision changed. Could not load the updated cart; refresh before trying again.");
    }
    return;
  }
  await refreshCart({ reconcile: true });
}

createButton.addEventListener("click", () => void createCart());
refreshButton.addEventListener("click", () => void refreshCart());
clearButton.addEventListener("click", () =>
  void mutateCart("DELETE", "/customers/me/cart/items", undefined, "Cart cleared."));
checkoutButton.addEventListener("click", () => {
  if (busy || attempt || !cart || cart.items.length === 0) return;
  saveAttempt({ customer_id: cart.customer_id, cart_id: cart.id, cart_revision: cart.revision });
  void doCheckout();
});
checkButton.addEventListener("click", () => void refreshCart({ reconcile: true }));
retryButton.addEventListener("click", () => void doCheckout());
void refreshCart();
