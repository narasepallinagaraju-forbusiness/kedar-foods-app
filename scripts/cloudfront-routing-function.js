function handler(event) {
  var request = event.request;
  var uri = request.uri;

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
