// assets/js/dashboard.js
// Dashboard global S&P 500 + Crypto

async function safeFetchJson(path) {
  try {
    const resp = await fetch(path);
    if (!resp.ok) {
      console.error(`Erreur HTTP sur ${path} : ${resp.status}`);
      return null;
    }
    return await resp.json();
  } catch (e) {
    console.error(`Erreur réseau sur ${path} :`, e);
    return null;
  }
}

/**
 * Compte le nombre de signaux dans un objet JSON de type :
 * { date_mise_a_jour: "...", picks: { TICKER: { ... }, ... } }
 */
function countSignals(data) {
  if (!data || !data.picks || typeof data.picks !== "object") return 0;
  return Object.keys(data.picks).length;
}

async function initDashboard() {
  // Récup des éléments DOM
  const elSp500Phoenix = document.getElementById("dash-sp500-phoenix-count");
  const elSp500Pullback = document.getElementById("dash-sp500-pullback-count");
  const elCryptoPhoenix = document.getElementById("dash-crypto-phoenix-count");
  const elCryptoPullback = document.getElementById("dash-crypto-pullback-count");
  const elTotalSp500 = document.getElementById("dash-total-sp500");
  const elTotalCrypto = document.getElementById("dash-total-crypto");

  // Valeurs par défaut (si le DOM n'est pas là, on sort proprement)
  if (!elSp500Phoenix || !elSp500Pullback || !elCryptoPhoenix || !elCryptoPullback || !elTotalSp500 || !elTotalCrypto) {
    console.error("Éléments du dashboard manquants dans le DOM.");
    return;
  }

  elSp500Phoenix.textContent = "…";
  elSp500Pullback.textContent = "…";
  elCryptoPhoenix.textContent = "…";
  elCryptoPullback.textContent = "…";
  elTotalSp500.textContent = "…";
  elTotalCrypto.textContent = "…";

  // Chargement des 4 fichiers de signaux en parallèle
  const [
    sp500PhoenixData,
    sp500PullbackData,
    cryptoPhoenixData,
    cryptoPullbackData
  ] = await Promise.all([
    safeFetchJson("data/sp500_breakout_pro.json"),
    safeFetchJson("data/sp500_pullback_pro.json"),
    safeFetchJson("data/crypto_breakout_pro.json"),
    safeFetchJson("data/crypto_pullback_pro.json")
  ]);

  // Comptage
  const sp500PhoenixCount = countSignals(sp500PhoenixData);
  const sp500PullbackCount = countSignals(sp500PullbackData);
  const cryptoPhoenixCount = countSignals(cryptoPhoenixData);
  const cryptoPullbackCount = countSignals(cryptoPullbackData);

  const totalSp500 = sp500PhoenixCount + sp500PullbackCount;
  const totalCrypto = cryptoPhoenixCount + cryptoPullbackCount;

  // Mise à jour du DOM
  elSp500Phoenix.textContent = String(sp500PhoenixCount);
  elSp500Pullback.textContent = String(sp500PullbackCount);
  elCryptoPhoenix.textContent = String(cryptoPhoenixCount);
  elCryptoPullback.textContent = String(cryptoPullbackCount);
  elTotalSp500.textContent = String(totalSp500);
  elTotalCrypto.textContent = String(totalCrypto);
}

document.addEventListener("DOMContentLoaded", initDashboard);
