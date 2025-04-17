package com.devopstraining.spring.api.azure.passwordlessdbapp;

import java.util.HashMap;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.beans.factory.annotation.Value;
import java.util.concurrent.ThreadLocalRandom;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@RestController
@RequestMapping("/api")
public class TodoController {

    private static final Logger logger = LoggerFactory.getLogger(TodoController.class);

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
            // Possible sleep times: 0 ms, 2000 ms, 4000 ms, 6000 ms
            int[] sleepOptions = {0, 2000, 4000, 6000};
            int sleepTime = sleepOptions[ThreadLocalRandom.current().nextInt(sleepOptions.length)];

            if (sleepTime > 0) {
                try {
                    logger.info("RANDOM_DELAYS: Sleeping for " + sleepTime + " milliseconds...");
                    Thread.sleep(sleepTime);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    logger.error("RANDOM_DELAYS: Sleep interrupted: " + e.getMessage());
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
    
}
