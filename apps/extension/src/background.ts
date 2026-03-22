chrome.runtime.onInstalled.addListener(() => {
  console.log('TruthLens extension installed');
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === 'TRUTHLENS_PING') {
    sendResponse({ ok: true });
  }
});
