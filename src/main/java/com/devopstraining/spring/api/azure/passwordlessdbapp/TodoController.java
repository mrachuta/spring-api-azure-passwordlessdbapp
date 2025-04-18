package com.devopstraining.spring.api.azure.passwordlessdbapp;

import java.util.HashMap;
import java.util.Map;
import java.util.List;
import java.util.ArrayList;
import java.util.Random;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.beans.factory.annotation.Value;
import java.util.concurrent.ThreadLocalRandom;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@RestController
@RequestMapping("/api")
public class TodoController {

    private static final Logger logger = LoggerFactory.getLogger(TodoController.class);
    private final Random random = new Random();

    @Value("${STYLE_VERSION:v1}")
    private String styleVersion;

    @Value("${RANDOM_DELAYS:false}")
    private Boolean randomDelays;

    private final TodoRepository todoRepository;

    public TodoController(TodoRepository todoRepository) {
        this.todoRepository = todoRepository;
    }

    @PostMapping("/task")
    @ResponseStatus(HttpStatus.CREATED)
    public Todo createTodo(@RequestBody Todo todo) {
        return todoRepository.save(todo);
    }

    @GetMapping("/task")
    public Iterable<Todo> getTodos() {
        if (randomDelays) {
        // 25% chance of delay
            if (random.nextInt(100) < 20) {
                try {
                    int halfSeconds = random.nextInt(9) + 2;
                    long sleepTime = halfSeconds * 500L;
                    logger.info("RANDOM_DELAYS: Sleeping for {} milliseconds...", sleepTime);
                    Thread.sleep(sleepTime);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    logger.error("RANDOM_DELAYS: Sleep interrupted: {}", e.getMessage());
                }
            }
        }
        return todoRepository.findAll();
    }

    @GetMapping("/config")
    public Map<String, Object> getConfigurationAsJson() {
        HashMap<String, Object> configMap = new HashMap<String, Object>();
        configMap.put("style_version", styleVersion);
        String tableStyle = (styleVersion.equals("v2")) ? "table-extra" : "table-standard";
        configMap.put("table_style", tableStyle);
        return configMap;
    }

    @GetMapping("/liveness")
    public Map<String, Object> getLivenessAsJson() {
        HashMap<String, Object> livenessMap = new HashMap<String, Object>();
        livenessMap.put("live", "true");
        return livenessMap;
    }

    @GetMapping("/readiness")
    public Map<String, Object> getReadinessAsJson() {
        HashMap<String, Object> readinessMap = new HashMap<String, Object>();
        readinessMap.put("ready", "true");
        return readinessMap;
    }

    @GetMapping("/test")
    public ResponseEntity<List<Map<String, Object>>> getTestListAsJson() {

        // 20% chance of delay
        if (random.nextInt(100) < 20) {
            try {
                int halfSeconds = random.nextInt(9) + 2; // 2 to 10
                long sleepTime = halfSeconds * 500L;
                logger.info("RANDOM_DELAYS: Sleeping for {} milliseconds...", sleepTime);
                Thread.sleep(sleepTime);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                logger.error("RANDOM_DELAYS: Sleep interrupted: {}", e.getMessage());
            }
        }

        // 10% chance of error
        if (random.nextInt(100) < 10) {
            int[] errorCodes = {502, 503, 504};
            int errorCode = errorCodes[random.nextInt(errorCodes.length)];
            String errorMessage = switch (errorCode) {
                case 502 -> "Bad Gateway";
                case 503 -> "Service Unavailable";
                case 504 -> "Gateway Timeout";
                default -> "Unexpected Error";
            };

            Map<String, Object> errorResponse = new HashMap<>();
            errorResponse.put("id", "error");
            errorResponse.put("description", "Error");
            errorResponse.put("details", errorMessage);
            errorResponse.put("done", false);

            logger.warn("RANDOM_ERRORS: Returning HTTP {} - {}", errorCode, errorMessage);
            return ResponseEntity.status(errorCode).body(List.of(errorResponse));
        }

        // Normal success response
        Map<String, Object> testMap = new HashMap<>();
        testMap.put("id", "1");
        testMap.put("description", "Success");
        testMap.put("details", "Hello from test page!");
        testMap.put("done", true);

        return ResponseEntity.ok(List.of(testMap));
    }
}
