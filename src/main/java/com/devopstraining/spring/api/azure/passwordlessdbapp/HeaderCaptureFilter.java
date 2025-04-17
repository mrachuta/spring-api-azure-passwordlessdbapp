package com.devopstraining.spring.api.azure.passwordlessdbapp;

import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

import static net.logstash.logback.argument.StructuredArguments.entries;

@Component
public class HeaderCaptureFilter implements Filter {

    private static final Logger log = LoggerFactory.getLogger(HeaderCaptureFilter.class);

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {

        if (request instanceof HttpServletRequest httpRequest) {
            // Capture all headers
            Map<String, String> headers = new HashMap<>();
            Collections.list(httpRequest.getHeaderNames())
                      .forEach(header -> headers.put(header, httpRequest.getHeader(header)));

            // Log with headers as nested JSON
            String methodSymbol = httpRequest.getMethod();
            String requestURI = httpRequest.getRequestURI();
            log.info("{} {}",
                methodSymbol,
                requestURI,
                entries(Map.of(
                    "http_headers", headers,
                    "method", methodSymbol,
                    "path", requestURI
                ))
            );
        }

        chain.doFilter(request, response);
    }
}
