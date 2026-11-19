export function deliveryDate(shipment) {
  if (shipment.status !== 'delivered') return shipment.eta;
  return (shipment.timeline.find(event => event.status === 'delivered')?.time || shipment.updatedAt).slice(0, 10);
}

export function validTrackingNumber(value) {
  return /^[A-Za-z0-9-]{6,40}$/.test(value);
}
