const CARD_SELECTOR = 'ytd-rich-item-renderer, ytd-video-renderer, [data-truthlens-card]';

function asElement(node: Node | null): Element | null {
  if (!node) {
    return null;
  }
  if (node instanceof Element) {
    return node;
  }
  return node.parentElement;
}

function isTruthLensOwnedElement(element: Element, overlayId: string): boolean {
  if (element.id === overlayId) {
    return true;
  }

  return Boolean(
    element.closest(
      [
        `#${overlayId}`,
        '.truthlens-card-flag',
        '.truthlens-review-prompt',
        '.truthlens-action-row',
        '.truthlens-details',
      ].join(', '),
    ),
  );
}

function isTruthLensOwnedNode(node: Node, overlayId: string): boolean {
  const element = asElement(node);
  return element ? isTruthLensOwnedElement(element, overlayId) : false;
}

function touchesRelevantCard(node: Node | null): boolean {
  const element = asElement(node);
  if (!element) {
    return false;
  }

  return (
    element.matches(CARD_SELECTOR) ||
    element.closest(CARD_SELECTOR) !== null ||
    element.querySelector(CARD_SELECTOR) !== null
  );
}

export function shouldRescoreFromMutations(
  mutations: MutationRecord[],
  overlayId: string,
): boolean {
  for (const mutation of mutations) {
    const targetElement = asElement(mutation.target);
    if (targetElement && isTruthLensOwnedElement(targetElement, overlayId)) {
      continue;
    }

    const changedNodes = [...mutation.addedNodes, ...mutation.removedNodes].filter(
      (node) => node.nodeType !== Node.COMMENT_NODE,
    );
    if (changedNodes.length === 0) {
      continue;
    }

    const nonOwnedNodes = changedNodes.filter((node) => !isTruthLensOwnedNode(node, overlayId));
    if (nonOwnedNodes.length === 0) {
      continue;
    }

    if (touchesRelevantCard(mutation.target)) {
      return true;
    }

    if (nonOwnedNodes.some((node) => touchesRelevantCard(node))) {
      return true;
    }
  }

  return false;
}
