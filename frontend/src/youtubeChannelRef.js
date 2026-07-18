export const youtubeChannelIdPattern = /^UC[A-Za-z0-9_-]{22}$/;

function cleanFields({ channelUrl = "", handle = "", channelId = "" } = {}) {
  return {
    channelUrl: String(channelUrl).trim(),
    handle: String(handle).trim(),
    channelId: String(channelId).trim(),
  };
}

export function officialChannelRef(fields) {
  const { channelUrl, handle, channelId } = cleanFields(fields);
  const values = [channelUrl, handle, channelId].filter(Boolean);
  if (!values.length) {
    return {
      ref: "",
      canonicalRef: "",
      error: "Kanal URL, @handle yoki channel ID maydonlaridan bittasini kiriting.",
    };
  }
  if (values.length > 1) {
    return { ref: "", canonicalRef: "", error: "Bitta rasmiy kanal manzilini tanlang." };
  }

  if (channelUrl) {
    const candidate = /^https?:\/\//i.test(channelUrl) ? channelUrl : `https://${channelUrl}`;
    try {
      const parsed = new URL(candidate);
      const hostname = parsed.hostname.toLowerCase();
      const isYoutube = hostname === "youtube.com" || hostname.endsWith(".youtube.com");
      const parts = parsed.pathname.split("/").filter(Boolean);
      const handlePart = parts[0] || "";
      const channelIdPart = parts[0] === "channel" ? parts[1] || "" : "";
      const usernamePart = parts[0] === "user" ? parts[1] || "" : "";
      if (!isYoutube || (!handlePart.startsWith("@") && !channelIdPart && !usernamePart)) {
        return {
          ref: "",
          canonicalRef: "",
          error: "Public YouTube kanal linkini kiriting: /@handle, /channel/UC... yoki /user/...",
        };
      }
      if (handlePart.startsWith("@") && handlePart.length > 1) {
        return { ref: candidate, canonicalRef: handlePart.toLowerCase(), error: "" };
      }
      if (youtubeChannelIdPattern.test(channelIdPart)) {
        return { ref: candidate, canonicalRef: channelIdPart, error: "" };
      }
      if (usernamePart) {
        return { ref: candidate, canonicalRef: `user:${usernamePart.toLowerCase()}`, error: "" };
      }
      return {
        ref: "",
        canonicalRef: "",
        error: "Public YouTube kanal linkini kiriting: /@handle, /channel/UC... yoki /user/...",
      };
    } catch {
      return { ref: "", canonicalRef: "", error: "YouTube kanal URL formati noto'g'ri." };
    }
  }

  if (handle) {
    if (!/^@[^\s/]+$/.test(handle)) {
      return {
        ref: "",
        canonicalRef: "",
        error: "Handle @ belgisi bilan yozilishi kerak, masalan @brand.",
      };
    }
    return { ref: handle, canonicalRef: handle.toLowerCase(), error: "" };
  }

  if (!youtubeChannelIdPattern.test(channelId)) {
    return {
      ref: "",
      canonicalRef: "",
      error: "Channel ID UC bilan boshlanadigan 24 belgili ID bo'lishi kerak.",
    };
  }
  return { ref: channelId, canonicalRef: channelId, error: "" };
}

export function officialChannelFieldsFromSource(source) {
  const empty = { channelUrl: "", handle: "", channelId: "" };
  if (!source || source.source_kind !== "channel") return empty;

  const sourceRef = String(source.source_ref || "").trim();
  if (sourceRef.startsWith("@")) {
    return { ...empty, handle: source.channel_handle || sourceRef };
  }
  if (sourceRef.toLowerCase().startsWith("user:")) {
    return { ...empty, channelUrl: `https://www.youtube.com/user/${sourceRef.slice("user:".length)}` };
  }
  if (youtubeChannelIdPattern.test(sourceRef)) {
    return { ...empty, channelId: sourceRef };
  }
  if (/^https?:\/\//i.test(sourceRef)) {
    return { ...empty, channelUrl: sourceRef };
  }
  if (source.channel_handle) {
    return { ...empty, handle: source.channel_handle };
  }
  if (youtubeChannelIdPattern.test(source.channel_id || "")) {
    return { ...empty, channelId: source.channel_id };
  }
  return empty;
}

export function canonicalOfficialChannelSourceRef(source) {
  if (!source || source.source_kind !== "channel") return "";
  const fields = officialChannelFieldsFromSource(source);
  const parsed = officialChannelRef(fields);
  return parsed.error ? "" : parsed.canonicalRef;
}
