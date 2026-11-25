// Drive Food4Thought's customer discovery page through the REST API, keeping
// presentation separate from backend rules and JSON storage. Render API text safely
// with textContent and ignore superseded requests so late responses cannot replace
// the current filter or selection.

import { requestJson } from "./api-client.js";
import { customerToken, customerRequest, customerError } from "./customer-session.js";
import { staffToken } from "./staff-session.js";
import { setStatus, showAvailability } from "./ui.js";

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function getJson(path) {
  let response;
  try {
    response = await requestJson(path, { timeoutMs: null });
  } catch {
    throw new ApiError(0, "Could not reach the server.");
  }

  const { body } = response;
  if (!response.ok) {
    const detail = body && typeof body.detail === "string" ? body.detail : null;
    throw new ApiError(response.status, detail || `Request failed (HTTP ${response.status}).`);
  }
  return body;
}

const listStatus = document.getElementById("list-status");
const restaurantList = document.getElementById("restaurant-list");
const filterForm = document.getElementById("filter-form");
const cuisineInput = document.getElementById("cuisine-input");
const clearFilter = document.getElementById("clear-filter");

const hero = document.getElementById("discovery-hero");
const discoveryGrid = document.getElementById("discovery-grid");
const detailsPanel = document.getElementById("restaurant-details");
const detailsStatus = document.getElementById("details-status");
const detailsContent = document.getElementById("details-content");
const detailsName = document.getElementById("details-name");
const detailsCuisine = document.getElementById("details-cuisine");
const detailsDescription = document.getElementById("details-description");
const editRestaurantLink = document.getElementById("edit-restaurant-link");
const menuStatus = document.getElementById("menu-status");
const menuList = document.getElementById("menu-list");

// Ignore responses from requests that a newer request has already replaced.
let listRequest = 0;
let detailsRequest = 0;

// Read the selection from the URL. A hand-typed link such as "#/restaurants/%"
// is not valid percent-encoding, so report it instead of letting it throw.
function readSelection() {
  const match = window.location.hash.match(/^#\/restaurants\/(.+)$/);
  if (!match) return { id: null, valid: true };
  try {
    return { id: decodeURIComponent(match[1]), valid: true };
  } catch {
    return { id: null, valid: false };
  }
}

function restaurantHash(restaurantId) {
  return `#/restaurants/${encodeURIComponent(restaurantId)}`;
}

async function loadRestaurants(cuisine) {
  const request = ++listRequest;
  const query = cuisine ? `?cuisine=${encodeURIComponent(cuisine)}` : "";
  setStatus(listStatus, "Loading restaurants…");
  restaurantList.replaceChildren();

  try {
    const restaurants = await getJson(`/restaurants${query}`);
    if (request !== listRequest) return;
    renderRestaurants(restaurants, cuisine);
  } catch (error) {
    if (request !== listRequest) return;
    setStatus(listStatus, `Could not load restaurants: ${error.message}`, "error");
  }
}

function renderRestaurants(restaurants, cuisine) {
  if (restaurants.length === 0) {
    setStatus(listStatus, cuisine ? `No restaurants serve "${cuisine}".` : "No restaurants yet.", "empty");
    return;
  }

  setStatus(listStatus, cuisine ? `Showing ${cuisine} restaurants.` : "");
  const selectedId = readSelection().id;

  for (const restaurant of restaurants) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "restaurant";
    button.dataset.restaurantId = restaurant.id;
    if (restaurant.id === selectedId) button.setAttribute("aria-current", "true");

    const name = document.createElement("span");
    name.className = "restaurant-name";
    name.textContent = restaurant.name;
    const cuisineLabel = document.createElement("span");
    cuisineLabel.className = "cuisine";
    cuisineLabel.textContent = restaurant.cuisine;
    const cover = document.createElement("span");
    cover.className = "restaurant-cover";
    cover.dataset.photo = restaurant.cuisine.trim().toLowerCase();
    cover.setAttribute("aria-hidden", "true");
    const summary = document.createElement("span");
    summary.className = "restaurant-summary";
    const description = document.createElement("span");
    description.className = "restaurant-description";
    description.textContent = restaurant.description;
    const next = document.createElement("span");
    next.className = "restaurant-next";
    next.textContent = "View menu \u2192";
    next.setAttribute("aria-hidden", "true");
    button.setAttribute("aria-label", restaurant.name + ", " + restaurant.cuisine);
    summary.append(name, cuisineLabel, description, next);
    button.append(cover, summary);

    button.addEventListener("click", () => {
      const hash = restaurantHash(restaurant.id);
      if (window.location.hash === hash) {
        // Same URL means no hashchange event, so reload directly. This lets a
        // customer retry after an error by clicking the restaurant again.
        showDetails(readSelection());
      } else {
        window.location.hash = hash;
      }
    });

    const item = document.createElement("li");
    item.append(button);
    restaurantList.append(item);
  }
}

function markSelected(restaurantId) {
  for (const button of restaurantList.querySelectorAll("button.restaurant")) {
    if (button.dataset.restaurantId === restaurantId) {
      button.setAttribute("aria-current", "true");
    } else {
      button.removeAttribute("aria-current");
    }
  }
}

async function showDetails(selection, focusHeading = false) {
  // Every selection change, including clearing it, invalidates older requests,
  // so a slow response can never redisplay a restaurant that is no longer selected.
  const request = ++detailsRequest;
  const restaurantId = selection.id;
  const showMenu = !selection.valid || restaurantId !== null;
  hero.hidden = showMenu;
  discoveryGrid.classList.toggle("has-selection", showMenu);
  detailsPanel.hidden = !showMenu;
  markSelected(restaurantId);
  detailsContent.hidden = true;
  editRestaurantLink.hidden = true;
  editRestaurantLink.removeAttribute("href");

  if (!selection.valid) {
    setStatus(detailsStatus, "That restaurant link isn't valid.", "error");
    return;
  }
  if (restaurantId === null) {
    setStatus(detailsStatus, "Select a restaurant to see its details and menu.");
    return;
  }

  const path = `/restaurants/${encodeURIComponent(restaurantId)}`;
  setStatus(detailsStatus, "Loading restaurant…");

  // Start both requests together, but handle them separately: the details are
  // the core requirement, so a menu failure must not hide them.
  const detailsPromise = getJson(path);
  const menuPromise = getJson(`${path}/menu`);
  menuPromise.catch(() => {}); // Handled below; ignored if the details fail first.

  let restaurant;
  try {
    restaurant = await detailsPromise;
  } catch (error) {
    if (request !== detailsRequest) return;
    const message =
      error.status === 404 ? "That restaurant doesn't exist." : `Could not load restaurant: ${error.message}`;
    setStatus(detailsStatus, message, "error");
    return;
  }
  if (request !== detailsRequest) return;
  renderRestaurant(restaurant);
  if (focusHeading) detailsName.focus();

  try {
    const menu = await menuPromise;
    if (request !== detailsRequest) return;
    renderMenu(menu, restaurantId);
  } catch (error) {
    if (request !== detailsRequest) return;
    setStatus(menuStatus, `Could not load the menu: ${error.message}`, "error");
  }
}

function renderRestaurant(restaurant) {
  detailsName.textContent = restaurant.name;
  detailsCuisine.textContent = restaurant.cuisine;
  detailsDescription.textContent = restaurant.description;
  editRestaurantLink.href = `edit-restaurant.html?id=${encodeURIComponent(restaurant.id)}`;
  editRestaurantLink.hidden = !staffToken();
  menuList.replaceChildren();
  setStatus(menuStatus, "Loading menu…");
  setStatus(detailsStatus, "");
  detailsContent.hidden = false;
}

function renderMenu(menu, restaurantId) {
  menuList.replaceChildren();
  if (menu.items.length === 0) {
    setStatus(menuStatus, "This restaurant has no menu items yet.", "empty");
    return;
  }
  setStatus(menuStatus, "");
  const selectionVersion = detailsRequest;
  for (const menuItem of menu.items) {
    const item = document.createElement("li");
    const heading = document.createElement("div");
    heading.className = "menu-item-heading";
    const name = document.createElement("span");
    name.className = "menu-item-name";
    name.textContent = menuItem.name;
    const price = document.createElement("span");
    price.className = "price";
    price.textContent = "$" + menuItem.price;
    heading.append(name, price);
    const description = document.createElement("p");
    description.textContent = menuItem.description;

    const controls = document.createElement("div");
    controls.className = "menu-item-controls";
    const availability = document.createElement("span");
    const addButton = document.createElement("button");
    addButton.type = "button";
    addButton.textContent = "Add to cart";
    addButton.setAttribute("aria-label", `Add ${menuItem.name} to cart`);
    addButton.addEventListener("click", async () => {
      if (addButton.disabled) return;
      if (!customerToken()) {
        setStatus(menuStatus, "Sign in through My account before adding to your cart.", "error");
        return;
      }
      addButton.disabled = true;
      setStatus(menuStatus, "Adding to cart…");
      try {
        // The backend requires an explicitly created active cart. PUT returns
        // the same cart when it already exists and never replaces its items.
        const created = await customerRequest("/customers/me/cart", { method: "PUT" });
        if (selectionVersion !== detailsRequest) return;
        if (!created.ok) {
          setStatus(menuStatus, customerError(created.status, created.body), "error");
          return;
        }
        if (typeof created.body?.id !== "string" || !Array.isArray(created.body.items)) {
          setStatus(menuStatus, "Cart response was unexpected. Open My cart to verify before retrying.", "error");
          return;
        }
        const result = await customerRequest("/customers/me/cart/items", {
          method: "POST", payload: { restaurant_id: restaurantId, item_id: menuItem.id, quantity: 1 },
        });
        if (selectionVersion !== detailsRequest) return;
        if (!result.ok) {
          setStatus(menuStatus, customerError(result.status, result.body), "error");
          return;
        }
        if (typeof result.body?.id !== "string" || !Array.isArray(result.body.items)) {
          setStatus(menuStatus, "Item addition could not be confirmed. Open My cart and refresh before retrying.", "error");
          return;
        }
        setStatus(menuStatus, `Added ${menuItem.name} to your cart. Open My cart to review it.`, "success");
      } catch {
        if (selectionVersion === detailsRequest) {
          // A request can reach the server even when its response is lost.
          setStatus(menuStatus, "Could not confirm item addition. Open My cart and refresh before trying again.", "error");
        }
      } finally {
        addButton.disabled = !menuItem.available;
      }
    });
    const body = document.createElement("div");
    body.className = "menu-item-body";
    const photo = document.createElement("span");
    photo.className = "menu-photo";
    photo.setAttribute("aria-hidden", "true");
    const dish = menuItem.name.toLowerCase().match(/\b(pizza|bowl)\b/);
    if (dish) photo.dataset.photo = dish[1];
    showAvailability(availability, menuItem.available);
    addButton.disabled = !menuItem.available;
    addButton.className = "primary-action";
    item.classList.toggle("unavailable", !menuItem.available);
    controls.append(availability, addButton);
    body.append(heading, description, controls);
    item.append(photo, body);
    menuList.append(item);
  }
}

filterForm.addEventListener("submit", (event) => {
  event.preventDefault();
  // A blank filter is a 422 from the API, so treat it as "show everything".
  loadRestaurants(cuisineInput.value.trim() || null);
});

clearFilter.addEventListener("click", () => {
  cuisineInput.value = "";
  loadRestaurants(null);
});

document.querySelector(".skip-link").addEventListener("click", event => {
  // The hash stores the selected restaurant, so skipping should only move focus.
  event.preventDefault();
  document.getElementById("main-content").focus();
});

window.addEventListener("hashchange", () => showDetails(readSelection(), true));

loadRestaurants(null);
showDetails(readSelection());
