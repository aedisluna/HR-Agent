window.HrAgentFiller = {
  setNativeValue(element, value) {
    if (!element) return false;

    const tag = element.tagName.toLowerCase();
    if (tag === "select") {
      const options = Array.from(element.options);
      const match =
        options.find((option) => option.text.trim().toLowerCase() === value.toLowerCase()) ||
        options.find((option) => option.value.toLowerCase() === value.toLowerCase()) ||
        options.find((option) => value.toLowerCase().includes(option.text.trim().toLowerCase()));
      if (match) {
        element.value = match.value;
        element.dispatchEvent(new Event("change", { bubbles: true }));
        return true;
      }
      return false;
    }

    if (tag === "textarea" || tag === "input") {
      element.focus();
      const prototype =
        tag === "textarea"
          ? window.HTMLTextAreaElement.prototype
          : window.HTMLInputElement.prototype;
      const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");
      if (descriptor?.set) {
        descriptor.set.call(element, value);
      } else {
        element.value = value;
      }
      element.dispatchEvent(new Event("input", { bubbles: true }));
      element.dispatchEvent(new Event("change", { bubbles: true }));
      return true;
    }

    return false;
  },

  applyMappings(fields, mappings) {
    const byId = new Map(fields.map((field) => [field.id, field]));
    const results = [];

    for (const mapping of mappings) {
      const field = byId.get(mapping.field_id);
      if (!field || !mapping.answer) {
        results.push({ ...mapping, filled: false });
        continue;
      }

      if (!mapping.fill) {
        results.push({ ...mapping, filled: false });
        continue;
      }

      const filled = this.setNativeValue(field.element, mapping.answer);
      results.push({ ...mapping, filled });
    }

    return results;
  },

  fillCoverLetterFields(fields, text) {
    if (!text) return 0;
    let filled = 0;
    for (const field of fields || []) {
      if (!HrAgentExtractors.isCoverLetterField(field.label)) continue;
      if (this.setNativeValue(field.element, text)) filled += 1;
    }
    return filled;
  },
};
