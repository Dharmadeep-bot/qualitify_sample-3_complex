function submitInvoicePayment() {
  const form = document.getElementById("invoice-pay-form");
  if (form) {
    form.requestSubmit();
  }
}
