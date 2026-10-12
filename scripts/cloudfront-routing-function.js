function handler(event) {
  var request = event.request;
  var uri = request.uri;

  var hostHeader = request.headers && request.headers.host;
  var host = hostHeader ? hostHeader.value.toLowerCase() : '';
  if (host.indexOf('www.') === 0) {
    var pairs = [];
    var query = request.querystring || {};
    Object.keys(query).forEach(function (key) {
      var entry = query[key];
      var values = entry.multiValue
        ? entry.multiValue.map(function (item) { return item.value; })
        : [entry.value];
      values.forEach(function (value) {
        pairs.push(value === '' ? key : key + '=' + value);
      });
    });
    return {
      statusCode: 301,
      statusDescription: 'Moved Permanently',
      headers: {
        location: {
          value:
            'https://' + host.substring(4) + uri + (pairs.length ? '?' + pairs.join('&') : ''),
        },
      },
    };
  }

  if (uri !== '/') {
    uri = uri.replace(/\/+$/, '');
    if (uri === '') {
      uri = '/';
    }
    request.uri = uri;
  }

  if (
    uri.indexOf('/_next/') === 0 ||
    uri.indexOf('/data/') === 0 ||
    uri.indexOf('/media/') === 0
  ) {
    return request;
  }

  if (uri === '/') {
    request.uri = '/index.html';
    return request;
  }

  var productMatch = uri.match(/^\/products\/([^/]+)$/);
  if (productMatch && productMatch[1].indexOf('.') === -1) {
    request.uri = '/products/_shell.html';
    return request;
  }

  var lastSegment = uri.substring(uri.lastIndexOf('/') + 1);
  if (lastSegment.indexOf('.') !== -1) {
    return request;
  }

  request.uri = uri.replace(/\/+$/, '') + '.html';
  return request;
}
